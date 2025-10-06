import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import grpc
from onvif import ONVIFCamera

from proto import onvif_pb2
from proto import onvif_pb2_grpc

logging.basicConfig(level=logging.INFO)


class OnvifService(onvif_pb2_grpc.OnvifServiceServicer):
    """ONVIF gRPC service aligned with onvif.proto and NestJS client."""

    def __init__(self):
        self.cameras = {}
        self._wsdl_dir = self._resolve_wsdl_dir()

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
        env_wsdl_dir = os.getenv("ONVIF_WSDL_DIR")
        if env_wsdl_dir and Path(env_wsdl_dir).is_dir():
            return env_wsdl_dir
        try:
            import wsdl  # type: ignore
            wsdl_path = Path(getattr(wsdl, "__file__", "")).parent
            if (wsdl_path / "devicemgmt.wsdl").exists():
                return str(wsdl_path)
        except Exception:
            pass
        # Fallback to venv site-packages wsdl dir if exists
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
        if key not in self.cameras:
            if self._wsdl_dir:
                self.cameras[key] = ONVIFCamera(host, port, username, password, wsdl_dir=self._wsdl_dir)
            else:
                self.cameras[key] = ONVIFCamera(host, port, username, password)
        return self.cameras[key]

    def _resolve_profile_token(self, camera, requested_token, require_ptz=False):
        media = camera.create_media_service()
        profiles = media.GetProfiles()
        if not profiles:
            raise ValueError("No profiles available on device")

        def resolve_token(token_or_index):
            if not token_or_index:
                return None
            for profile in profiles:
                if getattr(profile, 'token', None) == token_or_index:
                    return token_or_index
            try:
                index = int(token_or_index)
                if 0 <= index < len(profiles):
                    return profiles[index].token
            except (ValueError, IndexError):
                pass
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
        return profiles[0].token

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
            return onvif_pb2.GetCapabilitiesResponse(
                ptz_support=bool(getattr(capabilities, 'PTZ', None)),
                imaging_support=bool(getattr(capabilities, 'Imaging', None)),
                media_support=bool(getattr(capabilities, 'Media', None)),
                events_support=bool(getattr(capabilities, 'Events', None)),
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
            camera = self._get_camera(request.device_url, request.username, request.password)
            media = camera.create_media_service()
            profile_token = self._resolve_profile_token(camera, request.profile_token)
            get_uri = media.create_type('GetStreamUri')
            get_uri.ProfileToken = profile_token
            get_uri.StreamSetup = {'Stream': request.stream_type, 'Transport': {'Protocol': 'RTSP'}}
            stream_uri = media.GetStreamUri(get_uri)
            return onvif_pb2.GetStreamUriResponse(uri=getattr(stream_uri, 'Uri', '') or '', timeout="PT60S")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get stream URI: {e}")
            return onvif_pb2.GetStreamUriResponse()

    def AbsoluteMove(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            move_request = ptz.create_type('AbsoluteMove')
            move_request.ProfileToken = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
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
            move_request.ProfileToken = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
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
            move_request.ProfileToken = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
            if request.HasField('pan_tilt'):
                move_request.Velocity = {'PanTilt': {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}}
            if request.HasField('zoom'):
                move_request.Velocity = getattr(move_request, 'Velocity', {})
                move_request.Velocity['Zoom'] = {'x': request.zoom.position.x}
            if request.timeout > 0:
                move_request.Timeout = f"PT{request.timeout}S"
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
                stop_request.ProfileToken = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
                if request.pan_tilt:
                    stop_request.PanTilt = True
                if request.zoom:
                    stop_request.Zoom = True
                ptz.Stop(stop_request)
                return onvif_pb2.StopResponse(success=True, message="Stop command sent successfully")
            except Exception:
                try:
                    stop_data = {'ProfileToken': self._resolve_profile_token(camera, request.profile_token, require_ptz=True)}
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

    def GetPresets(self, request, context):
        try:
            camera = self._get_camera(request.device_url, request.username, request.password)
            ptz = camera.create_ptz_service()
            resolved_token = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
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
            resolved_profile_token = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
            # Resolve/validate preset token; if empty, auto-pick the first available
            resolved_preset_token = getattr(request, 'preset_token', None)
            try:
                presets = ptz.GetPresets({'ProfileToken': resolved_profile_token})
                if not resolved_preset_token or str(resolved_preset_token).strip() == "":
                    # Auto-select first available preset if any
                    for p in presets:
                        token = getattr(p, 'token', None)
                        if token:
                            resolved_preset_token = token
                            break
                # If still missing or not found among presets, return clear error
                if not resolved_preset_token or not any(getattr(p, 'token', None) == resolved_preset_token for p in presets):
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Preset token is missing or not found on device")
                    return onvif_pb2.GotoPresetResponse(success=False, message="Preset token is missing or not found on device")
            except Exception:
                # If presets retrieval fails, proceed and let device validate
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
            # Ensure a non-empty preset name regardless of client input
            effective_preset_name = self._generate_preset_name(getattr(request, 'preset_name', None))
            if not effective_preset_name or str(effective_preset_name).strip() == "":
                effective_preset_name = "Preset_1"
            create_request = ptz.create_type('SetPreset')
            try:
                create_request.ProfileToken = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
            except Exception:
                pass
            create_request.PresetName = effective_preset_name
            try:
                result = ptz.SetPreset(create_request)
            except Exception as e1:
                # Fallback: retry with a very simple non-empty name and alternative request shape
                try:
                    simple_name = "Preset1"
                    create_request.PresetName = simple_name
                    result = ptz.SetPreset(create_request)
                except Exception:
                    # Try dictionary-based request
                    req_dict = { 'PresetName': effective_preset_name }
                    try:
                        # Include profile token if resolvable
                        try:
                            req_dict['ProfileToken'] = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
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
            profile_token = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
            # Validate exists
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
                resolved_token = self._resolve_profile_token(camera, request.profile_token, require_ptz=True)
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