"""
Dummy ONVIF Service V2 - Mock Implementation
=============================================
This service simulates all ONVIF functionality using in-memory data.
No real camera is required. Perfect for testing and development.
"""

import logging
import threading
import time
from datetime import datetime
from concurrent import futures

import grpc
from proto import onvif_v2_pb2 as onvif_pb2
from proto import onvif_v2_pb2_grpc as onvif_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DummyOnvifServiceV2(onvif_pb2_grpc.OnvifServiceServicer):
    """Mock ONVIF gRPC service with in-memory data - no real camera needed."""

    def __init__(self):
        """Initialize the dummy service with mock data."""
        self.devices = {}  # Store device info by device_url
        self.presets = {}  # Store presets by device_url
        self.tours = {}  # Store preset tours by device_url
        self.ptz_status = {}  # Store PTZ status by device_url
        self.tour_threads = {}  # Store running tour threads
        logger.info("Dummy ONVIF Service V2 initialized with in-memory storage")

    def _get_device_key(self, device_url, username):
        """Generate a unique key for device identification."""
        return f"{device_url}:{username}"

    def _init_device_if_needed(self, device_url, username):
        """Initialize device data if it doesn't exist."""
        key = self._get_device_key(device_url, username)
        
        if key not in self.devices:
            self.devices[key] = {
                'manufacturer': 'Dummy ONVIF Camera',
                'model': 'Mock PTZ Camera V2',
                'firmware_version': '2.0.0',
                'serial_number': f'SN-{len(self.devices) + 1:04d}',
                'hardware_id': f'HW-{len(self.devices) + 1:04d}'
            }
        
        if key not in self.presets:
            # Initialize with 3 default presets
            self.presets[key] = [
                {
                    'token': 'preset_1',
                    'name': 'Home Position',
                    'pan_tilt': {'x': 0.0, 'y': 0.0},
                    'zoom': {'x': 0.0}
                },
                {
                    'token': 'preset_2',
                    'name': 'Entrance View',
                    'pan_tilt': {'x': 0.5, 'y': 0.2},
                    'zoom': {'x': 0.3}
                },
                {
                    'token': 'preset_3',
                    'name': 'Parking View',
                    'pan_tilt': {'x': -0.3, 'y': -0.1},
                    'zoom': {'x': 0.5}
                }
            ]
        
        if key not in self.tours:
            self.tours[key] = []
        
        if key not in self.ptz_status:
            self.ptz_status[key] = {
                'pan_tilt': {'x': 0.0, 'y': 0.0},
                'zoom': {'x': 0.0},
                'moving': False
            }

    # ============================================================================
    # Device Information Methods
    # ============================================================================

    def GetDeviceInformation(self, request, context):
        """Get device information."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            device = self.devices[key]
            
            logger.info(f"GetDeviceInformation for {key}")
            return onvif_pb2.GetDeviceInformationResponse(
                manufacturer=device['manufacturer'],
                model=device['model'],
                firmware_version=device['firmware_version'],
                serial_number=device['serial_number'],
                hardware_id=device['hardware_id']
            )
        except Exception as e:
            logger.error(f"GetDeviceInformation error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get device information: {e}")
            return onvif_pb2.GetDeviceInformationResponse()

    def GetCapabilities(self, request, context):
        """Get device capabilities."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            logger.info(f"GetCapabilities for {key}")
            return onvif_pb2.GetCapabilitiesResponse(
                ptz_support=True,
                imaging_support=True,
                media_support=True,
                events_support=True,
                ptz_preset_tour_support=True
            )
        except Exception as e:
            logger.error(f"GetCapabilities error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get capabilities: {e}")
            return onvif_pb2.GetCapabilitiesResponse()

    def GetProfiles(self, request, context):
        """Get media profiles."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            logger.info(f"GetProfiles for {key}")
            profiles = [
                onvif_pb2.Profile(
                    token='profile_1',
                    name='Main Stream',
                    is_fixed=False
                ),
                onvif_pb2.Profile(
                    token='profile_2',
                    name='Sub Stream',
                    is_fixed=False
                )
            ]
            return onvif_pb2.GetProfilesResponse(profiles=profiles)
        except Exception as e:
            logger.error(f"GetProfiles error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get profiles: {e}")
            return onvif_pb2.GetProfilesResponse()

    def GetStreamUri(self, request, context):
        """Get stream URI."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            profile_token = request.profile_token if request.HasField('profile_token') else 'profile_1'
            stream_type = request.stream_type or 'RTP-Unicast'
            
            logger.info(f"GetStreamUri for {key}, profile: {profile_token}, type: {stream_type}")
            
            # Generate mock RTSP URI
            uri = f"rtsp://{request.device_url.replace('http://', '').replace('https://', '')}/stream/{profile_token}"
            
            return onvif_pb2.GetStreamUriResponse(
                uri=uri,
                timeout='PT60S'
            )
        except Exception as e:
            logger.error(f"GetStreamUri error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get stream URI: {e}")
            return onvif_pb2.GetStreamUriResponse()

    # ============================================================================
    # PTZ Movement Methods
    # ============================================================================

    def AbsoluteMove(self, request, context):
        """Perform absolute PTZ move."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            if request.HasField('pan_tilt'):
                self.ptz_status[key]['pan_tilt']['x'] = request.pan_tilt.position.x
                self.ptz_status[key]['pan_tilt']['y'] = request.pan_tilt.position.y
                logger.info(f"AbsoluteMove PanTilt to ({request.pan_tilt.position.x}, {request.pan_tilt.position.y})")
            
            if request.HasField('zoom'):
                self.ptz_status[key]['zoom']['x'] = request.zoom.position.x
                logger.info(f"AbsoluteMove Zoom to {request.zoom.position.x}")
            
            self.ptz_status[key]['moving'] = True
            # Simulate movement completion after 0.5s
            threading.Timer(0.5, lambda: self._set_moving_false(key)).start()
            
            return onvif_pb2.AbsoluteMoveResponse(
                success=True,
                message="Absolute move command sent successfully"
            )
        except Exception as e:
            logger.error(f"AbsoluteMove error: {e}")
            return onvif_pb2.AbsoluteMoveResponse(
                success=False,
                message=f"Failed to perform absolute move: {e}"
            )

    def RelativeMove(self, request, context):
        """Perform relative PTZ move."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            if request.HasField('pan_tilt'):
                self.ptz_status[key]['pan_tilt']['x'] += request.pan_tilt.position.x
                self.ptz_status[key]['pan_tilt']['y'] += request.pan_tilt.position.y
                logger.info(f"RelativeMove PanTilt by ({request.pan_tilt.position.x}, {request.pan_tilt.position.y})")
            
            if request.HasField('zoom'):
                self.ptz_status[key]['zoom']['x'] += request.zoom.position.x
                logger.info(f"RelativeMove Zoom by {request.zoom.position.x}")
            
            self.ptz_status[key]['moving'] = True
            threading.Timer(0.5, lambda: self._set_moving_false(key)).start()
            
            return onvif_pb2.RelativeMoveResponse(
                success=True,
                message="Relative move command sent successfully"
            )
        except Exception as e:
            logger.error(f"RelativeMove error: {e}")
            return onvif_pb2.RelativeMoveResponse(
                success=False,
                message=f"Failed to perform relative move: {e}"
            )

    def ContinuousMove(self, request, context):
        """Perform continuous PTZ move."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            velocity_x = request.pan_tilt.position.x if request.HasField('pan_tilt') else 0.0
            velocity_y = request.pan_tilt.position.y if request.HasField('pan_tilt') else 0.0
            
            logger.info(f"ContinuousMove with velocity ({velocity_x}, {velocity_y}), timeout: {request.timeout}s")
            
            self.ptz_status[key]['moving'] = True
            if request.timeout > 0:
                threading.Timer(request.timeout, lambda: self._set_moving_false(key)).start()
            
            return onvif_pb2.ContinuousMoveResponse(
                success=True,
                message="Continuous move command sent successfully"
            )
        except Exception as e:
            logger.error(f"ContinuousMove error: {e}")
            return onvif_pb2.ContinuousMoveResponse(
                success=False,
                message=f"Failed to perform continuous move: {e}"
            )

    def Stop(self, request, context):
        """Stop PTZ movement."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            logger.info(f"Stop PTZ movement (pan_tilt={request.pan_tilt}, zoom={request.zoom})")
            self.ptz_status[key]['moving'] = False
            
            return onvif_pb2.StopResponse(
                success=True,
                message="Stop command sent successfully"
            )
        except Exception as e:
            logger.error(f"Stop error: {e}")
            return onvif_pb2.StopResponse(
                success=False,
                message=f"Failed to stop movement: {e}"
            )

    def GetPTZStatus(self, request, context):
        """Get current PTZ status."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            status = self.ptz_status[key]
            
            pan_tilt = onvif_pb2.PanTilt()
            pan_tilt.position.x = status['pan_tilt']['x']
            pan_tilt.position.y = status['pan_tilt']['y']
            
            zoom = onvif_pb2.Zoom()
            zoom.position.x = status['zoom']['x']
            
            logger.info(f"GetPTZStatus: PanTilt({status['pan_tilt']['x']}, {status['pan_tilt']['y']}), Zoom({status['zoom']['x']}), Moving={status['moving']}")
            
            return onvif_pb2.GetPTZStatusResponse(
                success=True,
                message="PTZ status retrieved successfully",
                pan_tilt=pan_tilt,
                zoom=zoom,
                moving=status['moving']
            )
        except Exception as e:
            logger.error(f"GetPTZStatus error: {e}")
            return onvif_pb2.GetPTZStatusResponse(
                success=False,
                message=f"Failed to get PTZ status: {e}"
            )

    def _set_moving_false(self, key):
        """Helper to set moving status to false."""
        if key in self.ptz_status:
            self.ptz_status[key]['moving'] = False

    # ============================================================================
    # Preset Methods
    # ============================================================================

    def GetPresets(self, request, context):
        """Get all presets."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            presets = []
            for preset_data in self.presets[key]:
                preset = onvif_pb2.Preset(
                    token=preset_data['token'],
                    name=preset_data['name']
                )
                preset.pan_tilt.position.x = preset_data['pan_tilt']['x']
                preset.pan_tilt.position.y = preset_data['pan_tilt']['y']
                preset.zoom.position.x = preset_data['zoom']['x']
                presets.append(preset)
            
            logger.info(f"GetPresets: returning {len(presets)} presets")
            return onvif_pb2.GetPresetsResponse(presets=presets)
        except Exception as e:
            logger.error(f"GetPresets error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get presets: {e}")
            return onvif_pb2.GetPresetsResponse()

    def GotoPreset(self, request, context):
        """Go to a preset position."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            # Find the preset
            preset = None
            for p in self.presets[key]:
                if p['token'] == request.preset_token:
                    preset = p
                    break
            
            if not preset:
                return onvif_pb2.GotoPresetResponse(
                    success=False,
                    message=f"Preset token '{request.preset_token}' not found"
                )
            
            # Move to preset position
            self.ptz_status[key]['pan_tilt']['x'] = preset['pan_tilt']['x']
            self.ptz_status[key]['pan_tilt']['y'] = preset['pan_tilt']['y']
            self.ptz_status[key]['zoom']['x'] = preset['zoom']['x']
            self.ptz_status[key]['moving'] = True
            threading.Timer(0.5, lambda: self._set_moving_false(key)).start()
            
            logger.info(f"GotoPreset: {preset['name']} ({request.preset_token})")
            return onvif_pb2.GotoPresetResponse(
                success=True,
                message=f"Moved to preset '{preset['name']}'"
            )
        except Exception as e:
            logger.error(f"GotoPreset error: {e}")
            return onvif_pb2.GotoPresetResponse(
                success=False,
                message=f"Failed to goto preset: {e}"
            )

    def SetPreset(self, request, context):
        """Set/update a preset at current position."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            preset_name = request.preset_name if request.HasField('preset_name') else f"Preset_{datetime.now().strftime('%H%M%S')}"
            
            # Check if preset with this name already exists
            preset_token = None
            for preset in self.presets[key]:
                if preset['name'] == preset_name:
                    preset_token = preset['token']
                    # Update existing preset
                    preset['pan_tilt'] = self.ptz_status[key]['pan_tilt'].copy()
                    preset['zoom'] = self.ptz_status[key]['zoom'].copy()
                    logger.info(f"SetPreset: Updated existing preset '{preset_name}' ({preset_token})")
                    break
            
            if not preset_token:
                # Create new preset
                preset_token = f"preset_{len(self.presets[key]) + 1}"
                new_preset = {
                    'token': preset_token,
                    'name': preset_name,
                    'pan_tilt': self.ptz_status[key]['pan_tilt'].copy(),
                    'zoom': self.ptz_status[key]['zoom'].copy()
                }
                self.presets[key].append(new_preset)
                logger.info(f"SetPreset: Created new preset '{preset_name}' ({preset_token})")
            
            return onvif_pb2.SetPresetResponse(
                success=True,
                message=f"Preset '{preset_name}' saved successfully",
                preset_token=preset_token
            )
        except Exception as e:
            logger.error(f"SetPreset error: {e}")
            return onvif_pb2.SetPresetResponse(
                success=False,
                message=f"Failed to set preset: {e}",
                preset_token=""
            )

    def RemovePreset(self, request, context):
        """Remove a preset."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            # Find and remove the preset
            for i, preset in enumerate(self.presets[key]):
                if preset['token'] == request.preset_token:
                    removed_preset = self.presets[key].pop(i)
                    logger.info(f"RemovePreset: Removed preset '{removed_preset['name']}' ({request.preset_token})")
                    return onvif_pb2.RemovePresetResponse(
                        success=True,
                        message=f"Preset '{removed_preset['name']}' removed successfully"
                    )
            
            return onvif_pb2.RemovePresetResponse(
                success=False,
                message=f"Preset token '{request.preset_token}' not found"
            )
        except Exception as e:
            logger.error(f"RemovePreset error: {e}")
            return onvif_pb2.RemovePresetResponse(
                success=False,
                message=f"Failed to remove preset: {e}"
            )

    def CreatePreset(self, request, context):
        """Create a new preset at specified or current position."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            # If position specified, move there first
            if request.HasField('pan_tilt'):
                self.ptz_status[key]['pan_tilt']['x'] = request.pan_tilt.position.x
                self.ptz_status[key]['pan_tilt']['y'] = request.pan_tilt.position.y
            
            if request.HasField('zoom'):
                self.ptz_status[key]['zoom']['x'] = request.zoom.position.x
            
            # Create preset at current/specified position
            preset_token = f"preset_{len(self.presets[key]) + 1}"
            preset_name = f"Preset_{datetime.now().strftime('%H%M%S')}"
            
            new_preset = {
                'token': preset_token,
                'name': preset_name,
                'pan_tilt': self.ptz_status[key]['pan_tilt'].copy(),
                'zoom': self.ptz_status[key]['zoom'].copy()
            }
            self.presets[key].append(new_preset)
            
            logger.info(f"CreatePreset: Created preset '{preset_name}' ({preset_token})")
            return onvif_pb2.CreatePresetResponse(
                success=True,
                message=f"Preset '{preset_name}' created successfully",
                preset_token=preset_token
            )
        except Exception as e:
            logger.error(f"CreatePreset error: {e}")
            return onvif_pb2.CreatePresetResponse(
                success=False,
                message=f"Failed to create preset: {e}",
                preset_token=""
            )

    # ============================================================================
    # Preset Tour Methods
    # ============================================================================

    def GetPresetTours(self, request, context):
        """Get all preset tours."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            pb_tours = []
            for tour_data in self.tours[key]:
                tour = onvif_pb2.PresetTour(
                    token=tour_data['token'],
                    name=tour_data['name'],
                    is_running=tour_data.get('is_running', False),
                    auto_start=tour_data.get('auto_start', False)
                )
                
                # Add starting condition if present
                if 'starting_condition' in tour_data:
                    condition = onvif_pb2.StartingCondition(
                        recurring_time=tour_data['starting_condition']['recurring_time'],
                        recurring_duration=tour_data['starting_condition']['recurring_duration'],
                        random_preset_order=tour_data['starting_condition']['random_preset_order']
                    )
                    tour.starting_condition.CopyFrom(condition)
                
                # Add steps
                for step_data in tour_data['steps']:
                    step = onvif_pb2.TourStep(
                        preset_token=step_data['preset_token'],
                        speed=step_data['speed'],
                        wait_time=step_data['wait_time']
                    )
                    tour.steps.append(step)
                
                pb_tours.append(tour)
            
            logger.info(f"GetPresetTours: returning {len(pb_tours)} tours")
            return onvif_pb2.GetPresetToursResponse(tours=pb_tours)
        except Exception as e:
            logger.error(f"GetPresetTours error: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get preset tours: {e}")
            return onvif_pb2.GetPresetToursResponse()

    def CreatePresetTour(self, request, context):
        """Create a new preset tour."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            tour_token = f"tour_{len(self.tours[key]) + 1}"
            tour_name = request.tour_name if request.HasField('tour_name') else f"Tour {len(self.tours[key]) + 1}"
            
            new_tour = {
                'token': tour_token,
                'name': tour_name,
                'steps': [],
                'is_running': False,
                'auto_start': request.auto_start if request.HasField('auto_start') else False,
                'stop_flag': False,
                'thread': None
            }
            
            # Add starting condition
            if request.HasField('starting_condition'):
                new_tour['starting_condition'] = {
                    'recurring_time': request.starting_condition.recurring_time,
                    'recurring_duration': request.starting_condition.recurring_duration,
                    'random_preset_order': request.starting_condition.random_preset_order
                }
            
            # Add steps
            for step in request.steps:
                step_data = {
                    'preset_token': step.preset_token,
                    'speed': step.speed,
                    'wait_time': step.wait_time
                }
                new_tour['steps'].append(step_data)
            
            self.tours[key].append(new_tour)
            
            logger.info(f"CreatePresetTour: Created tour '{tour_name}' ({tour_token}) with {len(new_tour['steps'])} steps")
            return onvif_pb2.CreatePresetTourResponse(
                success=True,
                message=f"Preset tour '{tour_name}' created successfully",
                tour_token=tour_token
            )
        except Exception as e:
            logger.error(f"CreatePresetTour error: {e}")
            return onvif_pb2.CreatePresetTourResponse(
                success=False,
                message=f"Failed to create preset tour: {e}",
                tour_token=""
            )

    def ModifyPresetTour(self, request, context):
        """Modify an existing preset tour."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            # Find the tour
            tour = None
            for t in self.tours[key]:
                if t['token'] == request.tour_token:
                    tour = t
                    break
            
            if not tour:
                return onvif_pb2.ModifyPresetTourResponse(
                    success=False,
                    message=f"Tour token '{request.tour_token}' not found"
                )
            
            # Update steps
            if request.steps:
                tour['steps'] = []
                for step in request.steps:
                    step_data = {
                        'preset_token': step.preset_token,
                        'speed': step.speed,
                        'wait_time': step.wait_time
                    }
                    tour['steps'].append(step_data)
            
            # Update auto_start
            if request.HasField('auto_start'):
                tour['auto_start'] = request.auto_start
            
            # Update starting condition
            if request.HasField('starting_condition'):
                tour['starting_condition'] = {
                    'recurring_time': request.starting_condition.recurring_time,
                    'recurring_duration': request.starting_condition.recurring_duration,
                    'random_preset_order': request.starting_condition.random_preset_order
                }
            
            logger.info(f"ModifyPresetTour: Modified tour '{tour['name']}' ({request.tour_token})")
            return onvif_pb2.ModifyPresetTourResponse(
                success=True,
                message=f"Preset tour '{tour['name']}' modified successfully"
            )
        except Exception as e:
            logger.error(f"ModifyPresetTour error: {e}")
            return onvif_pb2.ModifyPresetTourResponse(
                success=False,
                message=f"Failed to modify preset tour: {e}"
            )

    def OperatePresetTour(self, request, context):
        """Operate a preset tour (start/stop/pause/resume)."""
        try:
            self._init_device_if_needed(request.device_url, request.username)
            key = self._get_device_key(request.device_url, request.username)
            
            # Find the tour
            tour = None
            for t in self.tours[key]:
                if t['token'] == request.tour_token:
                    tour = t
                    break
            
            if not tour:
                return onvif_pb2.OperatePresetTourResponse(
                    success=False,
                    message=f"Tour token '{request.tour_token}' not found"
                )
            
            operation = request.operation.lower()
            
            if operation == "start":
                if tour['is_running']:
                    return onvif_pb2.OperatePresetTourResponse(
                        success=False,
                        message=f"Tour '{tour['name']}' is already running"
                    )
                
                tour['is_running'] = True
                tour['stop_flag'] = False
                
                # Start tour execution in background thread
                thread = threading.Thread(
                    target=self._execute_tour,
                    args=(key, tour),
                    daemon=True
                )
                tour['thread'] = thread
                thread.start()
                
                logger.info(f"OperatePresetTour: Started tour '{tour['name']}' ({request.tour_token})")
                return onvif_pb2.OperatePresetTourResponse(
                    success=True,
                    message=f"Preset tour '{tour['name']}' started successfully"
                )
                
            elif operation == "stop":
                if not tour['is_running']:
                    return onvif_pb2.OperatePresetTourResponse(
                        success=False,
                        message=f"Tour '{tour['name']}' is not running"
                    )
                
                tour['is_running'] = False
                tour['stop_flag'] = True
                
                if tour['thread'] and tour['thread'].is_alive():
                    tour['thread'].join(timeout=2)
                
                logger.info(f"OperatePresetTour: Stopped tour '{tour['name']}' ({request.tour_token})")
                return onvif_pb2.OperatePresetTourResponse(
                    success=True,
                    message=f"Preset tour '{tour['name']}' stopped successfully"
                )
                
            elif operation in ["pause", "resume"]:
                logger.info(f"OperatePresetTour: {operation.capitalize()}d tour '{tour['name']}' ({request.tour_token})")
                return onvif_pb2.OperatePresetTourResponse(
                    success=True,
                    message=f"Preset tour '{tour['name']}' {operation}d successfully"
                )
            else:
                return onvif_pb2.OperatePresetTourResponse(
                    success=False,
                    message=f"Invalid operation '{operation}'"
                )
                
        except Exception as e:
            logger.error(f"OperatePresetTour error: {e}")
            return onvif_pb2.OperatePresetTourResponse(
                success=False,
                message=f"Failed to operate preset tour: {e}"
            )

    def _execute_tour(self, device_key, tour):
        """Execute a preset tour in a loop."""
        logger.info(f"Tour execution started: {tour['name']}")
        
        try:
            while not tour['stop_flag']:
                for step in tour['steps']:
                    if tour['stop_flag']:
                        break
                    
                    # Find preset and move to it
                    preset = None
                    for p in self.presets[device_key]:
                        if p['token'] == step['preset_token']:
                            preset = p
                            break
                    
                    if preset:
                        logger.info(f"Tour '{tour['name']}': Moving to preset '{preset['name']}'")
                        self.ptz_status[device_key]['pan_tilt'] = preset['pan_tilt'].copy()
                        self.ptz_status[device_key]['zoom'] = preset['zoom'].copy()
                        self.ptz_status[device_key]['moving'] = True
                        
                        # Simulate movement time
                        time.sleep(0.5)
                        self.ptz_status[device_key]['moving'] = False
                        
                        # Wait at preset
                        wait_time = step['wait_time']
                        logger.info(f"Tour '{tour['name']}': Waiting {wait_time}s at preset '{preset['name']}'")
                        
                        for _ in range(wait_time):
                            if tour['stop_flag']:
                                break
                            time.sleep(1)
                    else:
                        logger.warning(f"Tour '{tour['name']}': Preset '{step['preset_token']}' not found")
                
                # Check if tour should continue (loop)
                if not tour['stop_flag']:
                    logger.info(f"Tour '{tour['name']}': Completed one cycle, restarting...")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Tour execution error: {e}")
        finally:
            tour['is_running'] = False
            logger.info(f"Tour execution stopped: {tour['name']}")


def serve(port=50051):
    """Start the dummy gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    onvif_pb2_grpc.add_OnvifServiceServicer_to_server(DummyOnvifServiceV2(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"🚀 Dummy ONVIF Service V2 started on port {port}")
    logger.info(f"📝 No real camera required - all operations use in-memory data")
    return server


if __name__ == '__main__':
    server = serve()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)

