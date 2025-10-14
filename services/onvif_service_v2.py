import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import grpc
from onvif import ONVIFCamera

from proto import onvif_v2_pb2 as onvif_pb2
from proto import onvif_v2_pb2_grpc as onvif_pb2_grpc
from config import get_config

config = get_config()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OnvifService(onvif_pb2_grpc.OnvifServiceServicer):
    """ONVIF gRPC service with intelligent native/manual preset tour support."""

    def __init__(self):
        self.cameras = {}
        self._wsdl_dir = self._resolve_wsdl_dir()
        self.preset_tours = {}  # Manual tour storage
        self._camera_capabilities_cache = {}  # Cache PTZ capabilities per camera
        self.manual_loop_lock = threading.Lock()

    def _generate_preset_name(self, base_hint=None):
        try:
            import datetime
            normalized_hint = (base_hint or "").strip()
            if normalized_hint:
                return normalized_hint
            now = datetime.datetime.now()
            return f"Preset_{now.strftime('%Y-%m-%d_%H-%M-%S')}"
        except Exception:
            return "Preset_Default"

    def _resolve_wsdl_dir(self):
        if config.onvif.wsdl_dir and Path(config.onvif.wsdl_dir).is_dir():
            return config.onvif.wsdl_dir
        
        env_wsdl_dir = os.getenv("ONVIF_WSDL_DIR")
        if env_wsdl_dir and Path(env_wsdl_dir).is_dir():
            return env_wsdl_dir
        
        try:
            import wsdl
            wsdl_path = Path(getattr(wsdl, "__file__", "")).parent
            if (wsdl_path / "devicemgmt.wsdl").exists():
                return str(wsdl_path)
        except Exception:
            pass
        
        try:
            repo_root = Path(__file__).resolve().parents[2]
            for site_pkg in (repo_root / "grpc_server/venv").rglob("site-packages"):
                wsdl_dir = site_pkg / "wsdl"
                if (wsdl_dir / "devicemgmt.wsdl").exists():
                    return str(wsdl_dir)
        except Exception:
            pass
        return None

    def _parse_device_url(self, device_url):
        try:
            parsed = urlparse(device_url)
            if parsed.scheme and parsed.netloc:
                host = parsed.hostname or device_url
                port = parsed.port or (443 if parsed.scheme == 'https' else 80)
                return host, port
        except Exception:
            pass
        if ':' in device_url:
            host_part, port_part = device_url.rsplit(':', 1)
            try:
                return host_part, int(port_part)
            except ValueError:
                return device_url, 80
        return device_url, 80

    def _get_camera(self, device_url, username, password):
        host, port = self._parse_device_url(device_url)
        key = f"{host}:{port}:{username}"
        
        if config.onvif.enable_caching and key in self.cameras:
            return self.cameras[key]
        
        if self._wsdl_dir:
            print(f"Using WSDL directory: {self._wsdl_dir}")
            print(f"Host: {host}, Port: {port}, Username: {username}, Password: {password}")
            camera = ONVIFCamera(host, port, username, password, wsdl_dir=self._wsdl_dir)
        else:
            print("No WSDL directory found, using default")
            camera = ONVIFCamera(host, port, username, password)
        
        if config.onvif.enable_caching:
            self.cameras[key] = camera
        
        return camera

    def _get_camera_key(self, device_url, username):
        """Generate a unique key for camera identification."""
        return f"{device_url}:{username}"

    def _check_native_preset_tour_support(self, camera, device_url, username) -> bool:
        """
        Check if camera supports native ONVIF preset tours using GetServiceCapabilities.
        Results are cached to avoid repeated checks.
        """
        camera_key = self._get_camera_key(device_url, username)
        
        # Return cached result if available
        if camera_key in self._camera_capabilities_cache:
            return self._camera_capabilities_cache[camera_key]
        
        logger.info(f"Checking native preset tour support for camera: {camera_key}")
        
        try:
            # Method 1: Use GetServiceCapabilities (most reliable)
            try:
                ptz = camera.create_ptz_service()
                ptz_caps = ptz.GetServiceCapabilities()
                
                if hasattr(ptz_caps, 'PresetTour') and ptz_caps.PresetTour:
                    logger.info(f"Camera {camera_key} supports native preset tours (via GetServiceCapabilities)")
                    self._camera_capabilities_cache[camera_key] = True
                    return True
                else:
                    logger.info(f"Camera {camera_key} does NOT support native preset tours (GetServiceCapabilities)")
                    self._camera_capabilities_cache[camera_key] = False
                    return False
            except AttributeError as e:
                logger.debug(f"GetServiceCapabilities not available: {e}")
            except Exception as e:
                logger.debug(f"GetServiceCapabilities failed: {e}")
            
            # Method 2: Check device capabilities for PTZ preset tour token
            try:
                ptz = camera.create_ptz_service()
                configs = ptz.GetConfigurations()
                for config_item in configs:
                    if (hasattr(config_item, 'DefaultPTZPresetTourToken') or 
                        hasattr(config_item, 'PresetTour')):
                        logger.info(f"Camera {camera_key} supports native preset tours (via GetConfigurations)")
                        self._camera_capabilities_cache[camera_key] = True
                        return True
            except Exception as e:
                logger.debug(f"GetConfigurations check failed: {e}")
            
            # Method 3: Try to call GetPresetTours
            try:
                ptz = camera.create_ptz_service()
                media = camera.create_media_service()
                profiles = media.GetProfiles()
                if profiles:
                    profile_token = profiles[0].token
                    get_tours_req = ptz.create_type('GetPresetTours')
                    get_tours_req.ProfileToken = profile_token
                    ptz.GetPresetTours(get_tours_req)
                    logger.info(f"Camera {camera_key} supports native preset tours (via GetPresetTours)")
                    self._camera_capabilities_cache[camera_key] = True
                    return True
            except AttributeError:
                logger.debug("GetPresetTours method not available")
            except Exception as e:
                logger.debug(f"GetPresetTours check failed: {e}")
            
            # Method 4: Check if CreatePresetTour method exists
            try:
                ptz = camera.create_ptz_service()
                media = camera.create_media_service()
                profiles = media.GetProfiles()
                if profiles:
                    profile_token = profiles[0].token
                    # Just check if the method exists by trying to create the type
                    create_req = ptz.create_type('CreatePresetTour')
                    logger.info(f"Camera {camera_key} supports native preset tours (method exists)")
                    self._camera_capabilities_cache[camera_key] = True
                    return True
            except AttributeError:
                logger.info(f"Camera {camera_key} does NOT support native preset tours (method missing)")
                self._camera_capabilities_cache[camera_key] = False
                return False
            except Exception:
                # Method exists but type creation failed - likely supports it
                logger.info(f"Camera {camera_key} likely supports native preset tours")
                self._camera_capabilities_cache[camera_key] = True
                return True
            
        except Exception as e:
            logger.warning(f"Error checking preset tour support: {e}")
        
        # Default to no support if all checks fail
        logger.info(f"Camera {camera_key} does NOT support native preset tours (default)")
        self._camera_capabilities_cache[camera_key] = False
        return False

    def _execute_manual_loop(self, camera, tour_data, profile_token):
        """Execute manual loop for cameras without native patrol support."""
        logger.info(f"Starting manual loop for tour: {tour_data['name']}")
        
        try:
            ptz = camera.create_ptz_service()
            
            while not tour_data['stop_manual_loop']:
                for step in tour_data['steps']:
                    if tour_data['stop_manual_loop']:
                        break
                    
                    logger.info(f"Manual loop - Moving to preset: {step['preset_token']} at speed: {step['speed']}")
                    
                    try:
                        goto_request = ptz.create_type('GotoPreset')
                        goto_request.ProfileToken = profile_token
                        goto_request.PresetToken = step['preset_token']
                        
                        if hasattr(goto_request, 'Speed') and step['speed'] > 0:
                            goto_request.Speed = {
                                'PanTilt': {'x': step['speed'], 'y': step['speed']},
                                'Zoom': {'x': step['speed']}
                            }
                        
                        ptz.GotoPreset(goto_request)
                        
                        wait_time = step['wait_time']
                        logger.info(f"Manual loop - Waiting {wait_time} seconds at preset: {step['preset_token']}")
                        
                        for _ in range(wait_time):
                            if tour_data['stop_manual_loop']:
                                logger.info(f"Manual loop stopped during wait at preset: {step['preset_token']}")
                                return
                            time.sleep(1)
                            
                    except Exception as e:
                        logger.warning(f"Failed to move to preset {step['preset_token']}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error in manual loop execution: {e}")
        finally:
            logger.info(f"Manual loop completed for tour: {tour_data['name']}")

    def _get_profile_token_safely(self, request):
        """Safely get profile_token from request, handling optional fields."""
        try:
            if hasattr(request, 'HasField') and request.HasField('profile_token'):
                return request.profile_token
            else:
                return None
        except Exception:
            return None

    def _log_request_details(self, request, method_name):
        """Log request details for debugging."""
        try:
            profile_token = self._get_profile_token_safely(request)
            has_field = hasattr(request, 'HasField') and request.HasField('profile_token')
            logger.info(f"{method_name} - profile_token: {profile_token} (type: {type(profile_token)}) - HasField: {has_field}")
        except Exception as e:
            logger.warning(f"{method_name} - Error logging request details: {e}")

    def _resolve_profile_token(self, camera, requested_token, require_ptz=False):
        media = camera.create_media_service()
        profiles = media.GetProfiles()
        if not profiles:
            raise ValueError("No profiles available on device")

        def resolve_token(token_or_index):
            if token_or_index is None or (isinstance(token_or_index, str) and token_or_index.strip() == ""):
                return None
            for profile in profiles:
                if getattr(profile, 'token', None) == token_or_index:
                    return token_or_index
            try:
                index = int(token_or_index)
                if 0 <= index < len(profiles):
                    return profiles[index].token
            except (ValueError, IndexError, TypeError):
                pass
            return None

        def find_substream_profile():
            for profile in profiles:
                token = getattr(profile, 'token', None)
                name = getattr(profile, 'Name', '').lower()
                if token and ('sub' in name or 'profile_2' in token.lower() or 'profile2' in token.lower()):
                    return token
            return None

        def find_available_profile():
            for profile in profiles:
                token = getattr(profile, 'token', None)
                if token:
                    return token
            return None

        if require_ptz:
            ptz = camera.create_ptz_service()
            if requested_token:
                resolved = resolve_token(requested_token)
                if resolved:
                    try:
                        test_request = ptz.create_type('SetPreset')
                        test_request.ProfileToken = resolved
                        test_request.PresetName = "Validate"
                        return resolved
                    except Exception:
                        pass
            for profile in profiles:
                token = getattr(profile, 'token', None)
                if not token:
                    continue
                try:
                    test_request = ptz.create_type('SetPreset')
                    test_request.ProfileToken = token
                    test_request.PresetName = "Validate"
                    return token
                except Exception:
                    continue
            return profiles[0].token

        if requested_token:
            resolved = resolve_token(requested_token)
            if resolved:
                return resolved
            raise ValueError("Requested profile token not found")
        
        substream_token = find_substream_profile()
        if substream_token:
            return substream_token
        
        available_token = find_available_profile()
        if available_token:
            return available_token
            
        return profiles[0].token

    # ============================================================================
    # Device Information Methods
    # ============================================================================

    def GetDeviceInformation(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            devicemgmt = camera.create_devicemgmt_service()
            info = devicemgmt.GetDeviceInformation()
            return onvif_pb2.GetDeviceInformationResponse(
                manufacturer=getattr(info, 'Manufacturer', '') or '',
                model=getattr(info, 'Model', '') or '',
                firmware_version=getattr(info, 'FirmwareVersion', '') or '',
                serial_number=getattr(info, 'SerialNumber', '') or '',
                hardware_id=getattr(info, 'HardwareId', '') or ''
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get device information: {e}")
            return onvif_pb2.GetDeviceInformationResponse()

    def GetCapabilities(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            devicemgmt = camera.create_devicemgmt_service()
            capabilities = devicemgmt.GetCapabilities()
            
            # Check for PTZ and native preset tour support
            ptz_support = bool(getattr(capabilities, 'PTZ', None))
            ptz_preset_tour_support = False
            
            if ptz_support:
                ptz_preset_tour_support = self._check_native_preset_tour_support(
                    camera, request.device_url, request.username
                )
            
            return onvif_pb2.GetCapabilitiesResponse(
                ptz_support=ptz_support,
                imaging_support=bool(getattr(capabilities, 'Imaging', None)),
                media_support=bool(getattr(capabilities, 'Media', None)),
                events_support=bool(getattr(capabilities, 'Events', None)),
                ptz_preset_tour_support=ptz_preset_tour_support,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get capabilities: {e}")
            return onvif_pb2.GetCapabilitiesResponse()

    def GetProfiles(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            media = camera.create_media_service()
            profiles = media.GetProfiles()
            return onvif_pb2.GetProfilesResponse(
                profiles=[
                    onvif_pb2.Profile(
                        token=getattr(p, 'token', ''),
                        name=getattr(p, 'Name', '') or '',
                        is_fixed=bool(getattr(p, 'fixed', False)),
                    )
                    for p in profiles
                ]
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get profiles: {e}")
            return onvif_pb2.GetProfilesResponse()

    def GetStreamUri(self, request, context):
        try:
            self._log_request_details(request, "GetStreamUri")
            camera = self._get_camera(request.device_url, request.username, request.password)
            media = camera.create_media_service()
            profile_token_value = self._get_profile_token_safely(request)
            profile_token = self._resolve_profile_token(camera, profile_token_value)
            get_uri = media.create_type('GetStreamUri')
            get_uri.ProfileToken = profile_token
            get_uri.StreamSetup = {'Stream': request.stream_type, 'Transport': {'Protocol': 'RTSP'}}
            stream_uri = media.GetStreamUri(get_uri)
            return onvif_pb2.GetStreamUriResponse(uri=getattr(stream_uri, 'Uri', '') or '', timeout="PT60S")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get stream URI: {e}")
            return onvif_pb2.GetStreamUriResponse()

    # ============================================================================
    # PTZ Movement Methods
    # ============================================================================

    def AbsoluteMove(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            move_request = ptz.create_type('AbsoluteMove')
            move_request.ProfileToken = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            if request.HasField('pan_tilt'):
                move_request.Position = {'PanTilt': {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}}
                move_request.Speed = {'PanTilt': {'x': request.pan_tilt.speed.x, 'y': request.pan_tilt.speed.y}}
            if request.HasField('zoom'):
                move_request.Position = getattr(move_request, 'Position', {})
                move_request.Position['Zoom'] = {'x': request.zoom.position.x}
                move_request.Speed = getattr(move_request, 'Speed', {})
                move_request.Speed['Zoom'] = {'x': request.zoom.speed.x}
            ptz.AbsoluteMove(move_request)
            return onvif_pb2.AbsoluteMoveResponse(success=True, message="Absolute move command sent successfully")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to perform absolute move: {e}")
            return onvif_pb2.AbsoluteMoveResponse(success=False, message=f"Failed to perform absolute move: {e}")

    def RelativeMove(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            move_request = ptz.create_type('RelativeMove')
            move_request.ProfileToken = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            if request.HasField('pan_tilt'):
                move_request.Translation = {'PanTilt': {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}}
                move_request.Speed = {'PanTilt': {'x': request.pan_tilt.speed.x, 'y': request.pan_tilt.speed.y}}
            if request.HasField('zoom'):
                move_request.Translation = getattr(move_request, 'Translation', {})
                move_request.Translation['Zoom'] = {'x': request.zoom.position.x}
                move_request.Speed = getattr(move_request, 'Speed', {})
                move_request.Speed['Zoom'] = {'x': request.zoom.speed.x}
            ptz.RelativeMove(move_request)
            return onvif_pb2.RelativeMoveResponse(success=True, message="Relative move command sent successfully")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to perform relative move: {e}")
            return onvif_pb2.RelativeMoveResponse(success=False, message=f"Failed to perform relative move: {e}")

    def ContinuousMove(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            move_request = ptz.create_type('ContinuousMove')
            move_request.ProfileToken = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            # Initialize velocity dictionary
            move_request.Velocity = {}
            
            if request.HasField('pan_tilt'):
                move_request.Velocity['PanTilt'] = {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}
            if request.HasField('zoom'):
                move_request.Velocity['Zoom'] = {'x': request.zoom.position.x}
            
            # Set a very long timeout to override camera's default 10-second timeout
            # Most cameras have a built-in 10-second timeout, so we set 1 hour (3600 seconds)
            move_request.Timeout = "PT86400S"
            ptz.ContinuousMove(move_request)
            return onvif_pb2.ContinuousMoveResponse(success=True, message="Continuous move command sent successfully")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to perform continuous move: {e}")
            return onvif_pb2.ContinuousMoveResponse(success=False, message=f"Failed to perform continuous move: {e}")

    def Stop(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            try:
                stop_request = ptz.create_type('Stop')
                stop_request.ProfileToken = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
                if request.pan_tilt:
                    stop_request.PanTilt = True
                if request.zoom:
                    stop_request.Zoom = True
                ptz.Stop(stop_request)
                return onvif_pb2.StopResponse(success=True, message="Stop command sent successfully")
            except Exception:
                try:
                    stop_data = {'ProfileToken': self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)}
                    if request.pan_tilt:
                        stop_data['PanTilt'] = True
                    if request.zoom:
                        stop_data['Zoom'] = True
                    ptz.Stop(stop_data)
                    return onvif_pb2.StopResponse(success=True, message="Stop command sent successfully")
                except Exception:
                    try:
                        ptz.Stop({})
                        return onvif_pb2.StopResponse(success=True, message="Stop command sent successfully")
                    except Exception as e3:
                        context.set_code(grpc.StatusCode.INTERNAL)
                        context.set_details(f"Failed to stop movement: {e3}")
                        return onvif_pb2.StopResponse(success=False, message=f"Failed to stop movement: {e3}")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to stop movement: {e}")
            return onvif_pb2.StopResponse(success=False, message=f"Failed to stop movement: {e}")

    def GetPTZStatus(self, request, context):
        try:
            self._log_request_details(request, "GetPTZStatus")
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            
            status_request = ptz.create_type('GetStatus')
            status_request.ProfileToken = profile_token
            status = ptz.GetStatus(status_request)
            
            pan_tilt = onvif_pb2.PanTilt()
            zoom = onvif_pb2.Zoom()
            moving = False
            
            if hasattr(status, 'Position') and status.Position:
                if hasattr(status.Position, 'PanTilt') and status.Position.PanTilt:
                    pan_tilt.position.x = getattr(status.Position.PanTilt, 'x', 0.0)
                    pan_tilt.position.y = getattr(status.Position.PanTilt, 'y', 0.0)
                if hasattr(status.Position, 'Zoom') and status.Position.Zoom:
                    zoom.position.x = getattr(status.Position.Zoom, 'x', 0.0)
            
            if hasattr(status, 'MoveStatus') and status.MoveStatus:
                if hasattr(status.MoveStatus, 'PanTilt') and status.MoveStatus.PanTilt:
                    moving = status.MoveStatus.PanTilt in ['MOVING', 'IDLE']
                elif hasattr(status.MoveStatus, 'Zoom') and status.MoveStatus.Zoom:
                    moving = status.MoveStatus.Zoom in ['MOVING', 'IDLE']
            
            return onvif_pb2.GetPTZStatusResponse(
                success=True,
                message="PTZ status retrieved successfully",
                pan_tilt=pan_tilt,
                zoom=zoom,
                moving=moving
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get PTZ status: {e}")
            return onvif_pb2.GetPTZStatusResponse(
                success=False,
                message=f"Failed to get PTZ status: {e}"
            )

    # ============================================================================
    # Preset Methods
    # ============================================================================

    def GetPresets(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            resolved_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            presets = ptz.GetPresets({'ProfileToken': resolved_token})
            out = []
            for preset in presets:
                pb = onvif_pb2.Preset(token=getattr(preset, 'token', ''), name=getattr(preset, 'Name', '') or '')
                if hasattr(preset, 'PTZPosition') and preset.PTZPosition:
                    if hasattr(preset.PTZPosition, 'PanTilt') and preset.PTZPosition.PanTilt:
                        pb.pan_tilt.position.x = getattr(preset.PTZPosition.PanTilt, 'x', 0.0)
                        pb.pan_tilt.position.y = getattr(preset.PTZPosition.PanTilt, 'y', 0.0)
                    if hasattr(preset.PTZPosition, 'Zoom') and preset.PTZPosition.Zoom:
                        pb.zoom.position.x = getattr(preset.PTZPosition.Zoom, 'x', 0.0)
                out.append(pb)
            return onvif_pb2.GetPresetsResponse(presets=out)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get presets: {e}")
            return onvif_pb2.GetPresetsResponse()

    def GotoPreset(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            resolved_profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            resolved_preset_token = getattr(request, 'preset_token', None)
            try:
                presets = ptz.GetPresets({'ProfileToken': resolved_profile_token})
                if not resolved_preset_token or str(resolved_preset_token).strip() == "":
                    for p in presets:
                        token = getattr(p, 'token', None)
                        if token:
                            resolved_preset_token = token
                            break
                if not resolved_preset_token or not any(getattr(p, 'token', None) == resolved_preset_token for p in presets):
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Preset token is missing or not found on device")
                    return onvif_pb2.GotoPresetResponse(success=False, message="Preset token is missing or not found on device")
            except Exception:
                if not resolved_preset_token or str(resolved_preset_token).strip() == "":
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Preset token is required")
                    return onvif_pb2.GotoPresetResponse(success=False, message="Preset token is required")
            goto_request = ptz.create_type('GotoPreset')
            goto_request.ProfileToken = resolved_profile_token
            goto_request.PresetToken = resolved_preset_token
            if request.HasField('pan_tilt_speed') or request.HasField('zoom_speed'):
                goto_request.Speed = {}
                if request.HasField('pan_tilt_speed'):
                    goto_request.Speed['PanTilt'] = {'x': request.pan_tilt_speed.position.x, 'y': request.pan_tilt_speed.position.y}
                if request.HasField('zoom_speed'):
                    goto_request.Speed['Zoom'] = {'x': request.zoom_speed.position.x}
            ptz.GotoPreset(goto_request)
            return onvif_pb2.GotoPresetResponse(success=True, message="Goto preset command sent successfully")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to goto preset: {e}")
            return onvif_pb2.GotoPresetResponse(success=False, message=f"Failed to goto preset: {e}")

    def SetPreset(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            effective_preset_name = self._generate_preset_name(getattr(request, 'preset_name', None))
            if not effective_preset_name or str(effective_preset_name).strip() == "":
                effective_preset_name = "Preset_1"
            create_request = ptz.create_type('SetPreset')
            try:
                create_request.ProfileToken = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            except Exception:
                pass
            create_request.PresetName = effective_preset_name
            try:
                result = ptz.SetPreset(create_request)
            except Exception as e1:
                try:
                    simple_name = "Preset1"
                    create_request.PresetName = simple_name
                    result = ptz.SetPreset(create_request)
                except Exception:
                    req_dict = { 'PresetName': effective_preset_name }
                    try:
                        try:
                            req_dict['ProfileToken'] = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
                        except Exception:
                            pass
                        result = ptz.SetPreset(req_dict)
                    except Exception as e3:
                        context.set_code(grpc.StatusCode.INTERNAL)
                        context.set_details(f"Failed to set preset: {e1}; retry/simple/dict failed: {e3}")
                        return onvif_pb2.SetPresetResponse(success=False, message=f"Failed to set preset: {e1}")
            preset_token = result.PresetToken if hasattr(result, 'PresetToken') else str(result)
            return onvif_pb2.SetPresetResponse(success=True, message="Preset set successfully", preset_token=preset_token)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to set preset: {e}")
            return onvif_pb2.SetPresetResponse(success=False, message=f"Failed to set preset: {e}")

    def RemovePreset(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            try:
                presets = ptz.GetPresets({'ProfileToken': profile_token})
                if not any(getattr(p, 'token', None) == request.preset_token for p in presets):
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Preset token not found")
                    return onvif_pb2.RemovePresetResponse(success=False, message="Preset token not found")
            except Exception:
                pass
            remove_request = ptz.create_type('RemovePreset')
            remove_request.ProfileToken = profile_token
            remove_request.PresetToken = request.preset_token
            ptz.RemovePreset(remove_request)
            return onvif_pb2.RemovePresetResponse(success=True, message="Preset removed successfully")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to remove preset: {e}")
            return onvif_pb2.RemovePresetResponse(success=False, message=f"Failed to remove preset: {e}")

    def CreatePreset(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            try:
                resolved_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            except Exception:
                resolved_token = None
            try:
                if resolved_token and (request.HasField('pan_tilt') or request.HasField('zoom')):
                    move_req = ptz.create_type('AbsoluteMove')
                    move_req.ProfileToken = resolved_token
                    if request.HasField('pan_tilt') and request.pan_tilt:
                        move_req.Position = getattr(move_req, 'Position', {})
                        move_req.Position['PanTilt'] = {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}
                        move_req.Speed = getattr(move_req, 'Speed', {})
                        move_req.Speed['PanTilt'] = {'x': request.pan_tilt.speed.x, 'y': request.pan_tilt.speed.y}
                    if request.HasField('zoom') and request.zoom:
                        move_req.Position = getattr(move_req, 'Position', {})
                        move_req.Position['Zoom'] = {'x': request.zoom.position.x}
                        move_req.Speed = getattr(move_req, 'Speed', {})
                        move_req.Speed['Zoom'] = {'x': request.zoom.speed.x}
                    try:
                        ptz.AbsoluteMove(move_req)
                    except Exception:
                        pass
            except Exception:
                pass
            generated_name = self._generate_preset_name(None)
            try:
                if resolved_token:
                    create_request = ptz.create_type('SetPreset')
                    create_request.ProfileToken = resolved_token
                    create_request.PresetName = generated_name
                    result = ptz.SetPreset(create_request)
                    preset_token = result.PresetToken if hasattr(result, 'PresetToken') else str(result)
                    return onvif_pb2.CreatePresetResponse(success=True, message="Preset created", preset_token=preset_token)
            except Exception:
                pass
            try:
                create_request = ptz.create_type('SetPreset')
                create_request.PresetName = generated_name
                result = ptz.SetPreset(create_request)
                preset_token = result.PresetToken if hasattr(result, 'PresetToken') else str(result)
                return onvif_pb2.CreatePresetResponse(success=True, message="Preset created", preset_token=preset_token)
            except Exception as e2:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Failed to create preset: {e2}")
                return onvif_pb2.CreatePresetResponse(success=False, message=f"Failed to create preset: {e2}")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to create preset: {e}")
            return onvif_pb2.CreatePresetResponse(success=False, message=f"Failed to create preset: {e}")

    def UpdatePreset(self, request, context):
        """Update an existing preset with new name, position, or zoom."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            
            # Validate that the preset exists
            try:
                presets = ptz.GetPresets({'ProfileToken': profile_token})
                if not any(getattr(p, 'token', None) == request.preset_token for p in presets):
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Preset token not found")
                    return onvif_pb2.UpdatePresetResponse(success=False, message="Preset token not found")
            except Exception:
                pass
            
            # If new position/zoom is provided, move to that position first
            if request.HasField('pan_tilt') or request.HasField('zoom'):
                try:
                    move_req = ptz.create_type('AbsoluteMove')
                    move_req.ProfileToken = profile_token
                    
                    if request.HasField('pan_tilt') and request.pan_tilt:
                        move_req.Position = getattr(move_req, 'Position', {})
                        move_req.Position['PanTilt'] = {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}
                        move_req.Speed = getattr(move_req, 'Speed', {})
                        move_req.Speed['PanTilt'] = {'x': request.pan_tilt.speed.x, 'y': request.pan_tilt.speed.y}
                    
                    if request.HasField('zoom') and request.zoom:
                        move_req.Position = getattr(move_req, 'Position', {})
                        move_req.Position['Zoom'] = {'x': request.zoom.position.x}
                        move_req.Speed = getattr(move_req, 'Speed', {})
                        move_req.Speed['Zoom'] = {'x': request.zoom.speed.x}
                    
                    ptz.AbsoluteMove(move_req)
                    # Wait a moment for the movement to complete
                    time.sleep(1)
                    logger.info(f"Moved to new position before updating preset: {request.preset_token}")
                except Exception as e:
                    logger.warning(f"Failed to move to new position before updating preset: {e}")
            
            # Update the preset at the current position without removing/recreating
            try:
                set_req = ptz.create_type('SetPreset')
                set_req.ProfileToken = profile_token
                
                # Only set PresetName if it's provided, otherwise rely on preset_token
                if request.HasField('preset_name') and request.preset_name:
                    set_req.PresetName = request.preset_name
                    logger.info(f"Updating preset {request.preset_token} with new name: {request.preset_name}")
                else:
                    logger.info(f"Updating preset {request.preset_token} at current position (no name change)")
                
                # Try to set the preset with the existing token if the device supports it
                try:
                    set_req.PresetToken = request.preset_token
                except AttributeError:
                    # Some devices don't support PresetToken in SetPreset
                    pass
                
                result = ptz.SetPreset(set_req)
                
                # Get the actual preset token from result
                updated_token = getattr(result, 'PresetToken', request.preset_token)
                
                return onvif_pb2.UpdatePresetResponse(
                    success=True, 
                    message=f"Preset updated successfully. Token: {updated_token}"
                )
                
            except Exception as e:
                logger.error(f"Failed to update preset: {e}")
                return onvif_pb2.UpdatePresetResponse(
                    success=False, 
                    message=f"Failed to update preset: {e}"
                )
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to update preset: {e}")
            return onvif_pb2.UpdatePresetResponse(success=False, message=f"Failed to update preset: {e}")

    # ============================================================================
    # Preset Tour Methods - Unified Interface
    # ============================================================================

    def GetPresetTours(self, request, context):
        """Get all preset tours - works with both native and manual tours."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            camera_key = self._get_camera_key(request.device_url, request.username)
            has_native_support = self._check_native_preset_tour_support(camera, request.device_url, request.username)
            
            pb_tours = []
            
            if has_native_support:
                # Get native tours
                try:
                    profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
                    ptz = camera.create_ptz_service()
                    get_tours_req = ptz.create_type('GetPresetTours')
                    get_tours_req.ProfileToken = profile_token
                    native_tours = ptz.GetPresetTours(get_tours_req)
                    
                    for native_tour in native_tours:
                        tour = onvif_pb2.PresetTour(
                            token=getattr(native_tour, 'token', '') or getattr(native_tour, 'Token', ''),
                            name=getattr(native_tour, 'Name', 'Native Tour'),
                            is_running=getattr(native_tour, 'Status', {}).get('State', 'Idle') == 'Running',
                            auto_start=getattr(native_tour, 'AutoStart', False)
                        )
                        
                        # Add starting condition if available
                        if hasattr(native_tour, 'StartingCondition'):
                            condition = onvif_pb2.StartingCondition(
                                recurring_time=getattr(native_tour.StartingCondition, 'RecurringTime', 0),
                                recurring_duration=getattr(native_tour.StartingCondition, 'RecurringDuration', 'PT10S'),
                                random_preset_order=getattr(native_tour.StartingCondition, 'RandomPresetOrder', False)
                            )
                            tour.starting_condition.CopyFrom(condition)
                        
                        # Add tour spots/steps
                        if hasattr(native_tour, 'TourSpot'):
                            for spot in native_tour.TourSpot:
                                step = onvif_pb2.TourStep(
                                    preset_token=getattr(spot, 'PresetDetail', {}).get('PresetToken', ''),
                                    speed=getattr(spot, 'Speed', {}).get('x', 0.5),
                                    wait_time=int(getattr(spot, 'StayTime', 'PT10S').replace('PT', '').replace('S', ''))
                                )
                                tour.steps.append(step)
                        
                        pb_tours.append(tour)
                    
                    logger.info(f"Retrieved {len(pb_tours)} native preset tours")
                except Exception as e:
                    logger.warning(f"Failed to get native tours: {e}")
            
            # Also include manual tours if any exist
            manual_tours = self.preset_tours.get(camera_key, [])
            for tour_data in manual_tours:
                tour = onvif_pb2.PresetTour(
                    token=tour_data['token'],
                    name=tour_data['name'] + " (Manual)",
                    is_running=tour_data.get('is_running', False),
                    auto_start=tour_data.get('auto_start', False)
                )
                
                if 'starting_condition' in tour_data:
                    condition = onvif_pb2.StartingCondition(
                        recurring_time=tour_data['starting_condition']['recurring_time'],
                        recurring_duration=tour_data['starting_condition']['recurring_duration'],
                        random_preset_order=tour_data['starting_condition']['random_preset_order']
                    )
                    tour.starting_condition.CopyFrom(condition)
                
                for step_data in tour_data['steps']:
                    step = onvif_pb2.TourStep(
                        preset_token=step_data['preset_token'],
                        speed=step_data['speed'],
                        wait_time=step_data['wait_time']
                    )
                    tour.steps.append(step)
                
                pb_tours.append(tour)
            
            logger.info(f"Returning {len(pb_tours)} total preset tours")
            return onvif_pb2.GetPresetToursResponse(tours=pb_tours)
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get preset tours: {e}")
            return onvif_pb2.GetPresetToursResponse()

    def CreatePresetTour(self, request, context):
        """Create a preset tour - uses native if supported, otherwise manual."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            camera_key = self._get_camera_key(request.device_url, request.username)
            has_native_support = self._check_native_preset_tour_support(camera, request.device_url, request.username)
            
            if has_native_support:
                logger.info("Creating native ONVIF preset tour")
                return self._create_native_tour(request, context, camera)
            else:
                logger.info("Creating manual preset tour (native not supported)")
                return self._create_manual_tour(request, context, camera_key)
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to create preset tour: {e}")
            return onvif_pb2.CreatePresetTourResponse(
                success=False,
                message=f"Failed to create preset tour: {e}"
            )

    def ModifyPresetTour(self, request, context):
        """Modify a preset tour - handles both native and manual tours."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            camera_key = self._get_camera_key(request.device_url, request.username)
            has_native_support = self._check_native_preset_tour_support(camera, request.device_url, request.username)
            
            # Check if it's a manual tour
            manual_tours = self.preset_tours.get(camera_key, [])
            is_manual_tour = any(t['token'] == request.tour_token for t in manual_tours)
            
            if is_manual_tour:
                logger.info(f"Modifying manual preset tour: {request.tour_token}")
                return self._modify_manual_tour(request, context, camera_key)
            elif has_native_support:
                logger.info(f"Modifying native preset tour: {request.tour_token}")
                return self._modify_native_tour(request, context, camera)
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Tour not found")
                return onvif_pb2.ModifyPresetTourResponse(
                    success=False,
                    message="Tour not found"
                )
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to modify preset tour: {e}")
            return onvif_pb2.ModifyPresetTourResponse(
                success=False,
                message=f"Failed to modify preset tour: {e}"
            )

    def OperatePresetTour(self, request, context):
        """Operate a preset tour - handles both native and manual tours."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            camera_key = self._get_camera_key(request.device_url, request.username)
            has_native_support = self._check_native_preset_tour_support(camera, request.device_url, request.username)
            
            # Check if it's a manual tour
            manual_tours = self.preset_tours.get(camera_key, [])
            is_manual_tour = any(t['token'] == request.tour_token for t in manual_tours)
            
            if is_manual_tour:
                logger.info(f"Operating manual preset tour: {request.tour_token}")
                return self._operate_manual_tour(request, context, camera, camera_key)
            elif has_native_support:
                logger.info(f"Operating native preset tour: {request.tour_token}")
                return self._operate_native_tour(request, context, camera)
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Tour not found")
                return onvif_pb2.OperatePresetTourResponse(
                    success=False,
                    message="Tour not found"
                )
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to operate preset tour: {e}")
            return onvif_pb2.OperatePresetTourResponse(
                success=False,
                message=f"Failed to operate preset tour: {e}"
            )

    def DeletePresetTour(self, request, context):
        """Delete a preset tour - handles both native and manual tours."""
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            camera_key = self._get_camera_key(request.device_url, request.username)
            has_native_support = self._check_native_preset_tour_support(camera, request.device_url, request.username)
            
            # Check if it's a manual tour first
            manual_tours = self.preset_tours.get(camera_key, [])
            is_manual_tour = any(t['token'] == request.tour_token for t in manual_tours)
            
            if is_manual_tour:
                logger.info(f"Deleting manual preset tour: {request.tour_token}")
                return self._delete_manual_tour(request, context, camera_key)
            elif has_native_support:
                logger.info(f"Deleting native preset tour: {request.tour_token}")
                return self._delete_native_tour(request, context, camera)
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Tour not found")
                return onvif_pb2.DeletePresetTourResponse(
                    success=False,
                    message="Tour not found"
                )
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to delete preset tour: {e}")
            return onvif_pb2.DeletePresetTourResponse(
                success=False,
                message=f"Failed to delete preset tour: {e}"
            )

    # ============================================================================
    # Native Preset Tour Implementation
    # ============================================================================

    def _create_native_tour(self, request, context, camera):
        """Create a native ONVIF preset tour."""
        try:
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            ptz = camera.create_ptz_service()
            
            create_req = ptz.create_type('CreatePresetTour')
            create_req.ProfileToken = profile_token
            
            preset_tour = {
                'AutoStart': request.auto_start if hasattr(request, 'auto_start') else False,
                'StartingCondition': {
                    'RecurringTime': request.starting_condition.recurring_time if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 0,
                    'RecurringDuration': request.starting_condition.recurring_duration if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 'PT10S',
                    'RandomPresetOrder': request.starting_condition.random_preset_order if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else False
                }
            }
            
            if hasattr(request, 'steps') and request.steps:
                tour_spots = []
                for step in request.steps:
                    tour_spot = {
                        'PresetDetail': {'PresetToken': step.preset_token},
                        'Speed': {'PanTilt': {'x': step.speed, 'y': step.speed}, 'Zoom': {'x': step.speed}},
                        'StayTime': f'PT{step.wait_time}S'
                    }
                    tour_spots.append(tour_spot)
                preset_tour['TourSpot'] = tour_spots
            
            create_req.PresetTour = preset_tour
            result = ptz.CreatePresetTour(create_req)
            tour_token = result if isinstance(result, str) else getattr(result, 'Token', 'NativeTour_1')
            
            logger.info(f"Created native preset tour with token: {tour_token}")
            return onvif_pb2.CreatePresetTourResponse(
                success=True,
                message="Native preset tour created successfully",
                tour_token=tour_token
            )
            
        except Exception as e:
            logger.error(f"Failed to create native tour: {e}")
            raise

    def _modify_native_tour(self, request, context, camera):
        """Modify a native ONVIF preset tour."""
        try:
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            ptz = camera.create_ptz_service()
            
            modify_req = ptz.create_type('ModifyPresetTour')
            modify_req.ProfileToken = profile_token
            
            preset_tour = {
                'Token': request.tour_token,
                'AutoStart': request.auto_start if hasattr(request, 'auto_start') else False,
                'StartingCondition': {
                    'RecurringTime': request.starting_condition.recurring_time if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 0,
                    'RecurringDuration': request.starting_condition.recurring_duration if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 'PT10S',
                    'RandomPresetOrder': request.starting_condition.random_preset_order if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else False
                }
            }
            
            if hasattr(request, 'steps') and request.steps:
                tour_spots = []
                for step in request.steps:
                    tour_spot = {
                        'PresetDetail': {'PresetToken': step.preset_token},
                        'Speed': {'PanTilt': {'x': step.speed, 'y': step.speed}, 'Zoom': {'x': step.speed}},
                        'StayTime': f'PT{step.wait_time}S'
                    }
                    tour_spots.append(tour_spot)
                preset_tour['TourSpot'] = tour_spots
            
            modify_req.PresetTour = preset_tour
            ptz.ModifyPresetTour(modify_req)
            
            logger.info(f"Modified native preset tour: {request.tour_token}")
            return onvif_pb2.ModifyPresetTourResponse(
                success=True,
                message="Native preset tour modified successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to modify native tour: {e}")
            raise

    def _operate_native_tour(self, request, context, camera):
        """Operate a native ONVIF preset tour."""
        try:
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            ptz = camera.create_ptz_service()
            
            operate_req = ptz.create_type('OperatePresetTour')
            operate_req.ProfileToken = profile_token
            operate_req.PresetTourToken = request.tour_token
            operate_req.Operation = request.operation.capitalize()
            
            ptz.OperatePresetTour(operate_req)
            
            logger.info(f"Operated native preset tour: {request.tour_token} with operation: {request.operation}")
            return onvif_pb2.OperatePresetTourResponse(
                success=True,
                message=f"Native preset tour operation '{request.operation}' completed successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to operate native tour: {e}")
            raise

    def _delete_native_tour(self, request, context, camera):
        """Delete a native ONVIF preset tour."""
        try:
            profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
            ptz = camera.create_ptz_service()
            
            delete_req = ptz.create_type('RemovePresetTour')
            delete_req.ProfileToken = profile_token
            delete_req.PresetTourToken = request.tour_token
            
            ptz.RemovePresetTour(delete_req)
            
            logger.info(f"Deleted native preset tour: {request.tour_token}")
            return onvif_pb2.DeletePresetTourResponse(
                success=True,
                message="Native preset tour deleted successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to delete native tour: {e}")
            raise

    # ============================================================================
    # Manual Preset Tour Implementation
    # ============================================================================

    def _create_manual_tour(self, request, context, camera_key):
        """Create a manual preset tour when native support is unavailable."""
        if camera_key not in self.preset_tours:
            self.preset_tours[camera_key] = []
        
        new_token = f"ManualTour_{len(self.preset_tours[camera_key]) + 1}"
        
        new_tour = {
            'token': new_token,
            'name': request.tour_name or f"Manual Tour {len(self.preset_tours[camera_key]) + 1}",
            'steps': [],
            'is_running': False,
            'manual_loop_thread': None,
            'stop_manual_loop': False,
            'auto_start': request.auto_start if hasattr(request, 'auto_start') else False,
            'starting_condition': {
                'recurring_time': request.starting_condition.recurring_time if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 0,
                'recurring_duration': request.starting_condition.recurring_duration if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 'PT10S',
                'random_preset_order': request.starting_condition.random_preset_order if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else False
            }
        }
        
        # Add steps if provided
        if hasattr(request, 'steps') and request.steps:
            for step in request.steps:
                step_data = {
                    'preset_token': step.preset_token,
                    'speed': step.speed,
                    'wait_time': step.wait_time
                }
                new_tour['steps'].append(step_data)
        
        self.preset_tours[camera_key].append(new_tour)
        
        logger.info(f"Created manual preset tour: {new_tour['name']} with token: {new_token}")
        return onvif_pb2.CreatePresetTourResponse(
            success=True,
            message="Manual preset tour created successfully",
            tour_token=new_token
        )

    def _modify_manual_tour(self, request, context, camera_key):
        """Modify a manual preset tour."""
        tours = self.preset_tours.get(camera_key, [])
        
        for tour_data in tours:
            if tour_data['token'] == request.tour_token:
                # Update steps if provided
                if hasattr(request, 'steps') and request.steps:
                    tour_data['steps'] = []
                    for step in request.steps:
                        step_data = {
                            'preset_token': step.preset_token,
                            'speed': step.speed,
                            'wait_time': step.wait_time
                        }
                        tour_data['steps'].append(step_data)
                        logger.info(f"Added step - Preset: {step.preset_token}, Speed: {step.speed}, Wait: {step.wait_time}s")
                
                # Update auto_start and starting_condition
                if hasattr(request, 'auto_start'):
                    tour_data['auto_start'] = request.auto_start
                
                if hasattr(request, 'starting_condition') and request.HasField('starting_condition'):
                    tour_data['starting_condition'] = {
                        'recurring_time': request.starting_condition.recurring_time,
                        'recurring_duration': request.starting_condition.recurring_duration,
                        'random_preset_order': request.starting_condition.random_preset_order
                    }
                
                logger.info(f"Modified manual preset tour: {request.tour_token}")
                return onvif_pb2.ModifyPresetTourResponse(
                    success=True,
                    message="Manual preset tour modified successfully"
                )
        
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Manual tour not found")
        return onvif_pb2.ModifyPresetTourResponse(
            success=False,
            message="Manual tour not found"
        )

    def _operate_manual_tour(self, request, context, camera, camera_key):
        """Operate a manual preset tour."""
        tours = self.preset_tours.get(camera_key, [])
        
        for tour_data in tours:
            if tour_data['token'] == request.tour_token:
                profile_token = self._resolve_profile_token(camera, self._get_profile_token_safely(request), require_ptz=True)
                
                if request.operation.lower() == "start":
                    if tour_data['is_running']:
                        return onvif_pb2.OperatePresetTourResponse(
                            success=False,
                            message="Manual tour is already running"
                        )
                    
                    tour_data['is_running'] = True
                    tour_data['stop_manual_loop'] = False
                    
                    logger.info(f"Starting manual loop for tour: {tour_data['name']}")
                    tour_data['manual_loop_thread'] = threading.Thread(
                        target=self._execute_manual_loop,
                        args=(camera, tour_data, profile_token),
                        daemon=True
                    )
                    tour_data['manual_loop_thread'].start()
                    
                elif request.operation.lower() == "stop":
                    if not tour_data['is_running']:
                        return onvif_pb2.OperatePresetTourResponse(
                            success=False,
                            message="Manual tour is not running"
                        )
                    
                    tour_data['is_running'] = False
                    tour_data['stop_manual_loop'] = True
                    
                    if tour_data['manual_loop_thread'] and tour_data['manual_loop_thread'].is_alive():
                        logger.info(f"Stopping manual loop for tour: {tour_data['name']}")
                        tour_data['manual_loop_thread'].join(timeout=5)
                    
                elif request.operation.lower() in ["pause", "resume"]:
                    logger.info(f"{request.operation.capitalize()}d manual tour: {tour_data['name']}")
                    
                else:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Invalid operation")
                    return onvif_pb2.OperatePresetTourResponse(
                        success=False,
                        message="Invalid operation"
                    )
                
                return onvif_pb2.OperatePresetTourResponse(
                    success=True,
                    message=f"Manual tour operation '{request.operation}' completed successfully"
                )
        
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Manual tour not found")
        return onvif_pb2.OperatePresetTourResponse(
            success=False,
            message="Manual tour not found"
        )

    def _delete_manual_tour(self, request, context, camera_key):
        """Delete a manual preset tour."""
        tours = self.preset_tours.get(camera_key, [])
        
        for i, tour_data in enumerate(tours):
            if tour_data['token'] == request.tour_token:
                # Stop the tour if it's running
                if tour_data.get('is_running', False):
                    tour_data['is_running'] = False
                    tour_data['stop_manual_loop'] = True
                    
                    if tour_data.get('manual_loop_thread') and tour_data['manual_loop_thread'].is_alive():
                        logger.info(f"Stopping manual loop before deletion for tour: {tour_data['name']}")
                        tour_data['manual_loop_thread'].join(timeout=5)
                
                # Remove the tour from the list
                del self.preset_tours[camera_key][i]
                
                logger.info(f"Deleted manual preset tour: {request.tour_token}")
                return onvif_pb2.DeletePresetTourResponse(
                    success=True,
                    message="Manual preset tour deleted successfully"
                )
        
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Manual tour not found")
        return onvif_pb2.DeletePresetTourResponse(
            success=False,
            message="Manual tour not found"
        )

    
        """
        Legacy method - now redirects to OperatePresetTour which auto-detects support.
        Kept for backward compatibility.
        """
        logger.warning("OperateNativePresetTour is deprecated, use OperatePresetTour instead")
        return self.OperatePresetTour(request, context)