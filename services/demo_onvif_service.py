import logging
import grpc
from proto import onvif_pb2
from proto import onvif_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DemoOnvifService(onvif_pb2_grpc.OnvifServiceServicer):
    """
    Demo ONVIF gRPC service with hardcoded responses.
    This service provides mock ONVIF camera functionality for testing purposes.
    No URLs or network connections required - pure PTZ simulation.
    """

    def __init__(self):
        # Hardcoded demo camera information
        self.demo_device_info = {
            'manufacturer': 'Demo Camera Corp',
            'model': 'DC-IP2000',
            'firmware_version': '1.2.3.4',
            'serial_number': 'DEMO123456789',
            'hardware_id': 'HW-DEMO-001'
        }
        
        # Hardcoded capabilities
        self.demo_capabilities = {
            'ptz_support': True,
            'imaging_support': True,
            'media_support': True,
            'events_support': False
        }
        
        # Hardcoded profiles
        self.demo_profiles = [
            {
                'token': 'Profile_1',
                'name': 'Main Stream',
                'is_fixed': True
            },
            {
                'token': 'Profile_2', 
                'name': 'Sub Stream',
                'is_fixed': False
            }
        ]
        
        # Hardcoded presets
        self.demo_presets = [
            {
                'token': 'Preset_1',
                'name': 'Home Position',
                'pan_tilt': {'x': 0.0, 'y': 0.0},
                'zoom': {'x': 0.0}
            },
            {
                'token': 'Preset_2',
                'name': 'Left Corner',
                'pan_tilt': {'x': -1.0, 'y': 0.5},
                'zoom': {'x': 0.2}
            },
            {
                'token': 'Preset_3',
                'name': 'Right Corner',
                'pan_tilt': {'x': 1.0, 'y': 0.5},
                'zoom': {'x': 0.2}
            }
        ]
        
        logger.info("Demo ONVIF Service initialized - No URLs required for PTZ operations")

    def GetDeviceInformation(self, request, context):
        """Return hardcoded device information."""
        logger.info("GetDeviceInformation called")
        
        return onvif_pb2.GetDeviceInformationResponse(
            manufacturer=self.demo_device_info['manufacturer'],
            model=self.demo_device_info['model'],
            firmware_version=self.demo_device_info['firmware_version'],
            serial_number=self.demo_device_info['serial_number'],
            hardware_id=self.demo_device_info['hardware_id']
        )

    def GetCapabilities(self, request, context):
        """Return hardcoded device capabilities."""
        logger.info("GetCapabilities called")
        
        return onvif_pb2.GetCapabilitiesResponse(
            ptz_support=self.demo_capabilities['ptz_support'],
            imaging_support=self.demo_capabilities['imaging_support'],
            media_support=self.demo_capabilities['media_support'],
            events_support=self.demo_capabilities['events_support']
        )

    def GetProfiles(self, request, context):
        """Return hardcoded media profiles."""
        logger.info("GetProfiles called")
        
        profiles = []
        for profile_data in self.demo_profiles:
            profile = onvif_pb2.Profile(
                token=profile_data['token'],
                name=profile_data['name'],
                is_fixed=profile_data['is_fixed']
            )
            profiles.append(profile)
        
        return onvif_pb2.GetProfilesResponse(profiles=profiles)

    def GetStreamUri(self, request, context):
        """Return empty stream URI since PTZ doesn't need URLs."""
        logger.info("GetStreamUri called - returning empty URI for PTZ-only demo")
        
        return onvif_pb2.GetStreamUriResponse(
            uri="",
            timeout="PT60S"
        )

    def AbsoluteMove(self, request, context):
        """Simulate absolute PTZ movement - no URL required."""
        logger.info("AbsoluteMove called")
        
        if request.HasField('pan_tilt'):
            logger.info(f"Demo: Moving to pan: {request.pan_tilt.position.x}, tilt: {request.pan_tilt.position.y}")
        
        if request.HasField('zoom'):
            logger.info(f"Demo: Zooming to: {request.zoom.position.x}")
        
        return onvif_pb2.AbsoluteMoveResponse(
            success=True,
            message="Demo: Absolute move command simulated successfully"
        )

    def RelativeMove(self, request, context):
        """Simulate relative PTZ movement - no URL required."""
        logger.info("RelativeMove called")
        
        if request.HasField('pan_tilt'):
            logger.info(f"Demo: Moving relative pan: {request.pan_tilt.position.x}, tilt: {request.pan_tilt.position.y}")
        
        if request.HasField('zoom'):
            logger.info(f"Demo: Zooming relative: {request.zoom.position.x}")
        
        return onvif_pb2.RelativeMoveResponse(
            success=True,
            message="Demo: Relative move command simulated successfully"
        )

    def ContinuousMove(self, request, context):
        """Simulate continuous PTZ movement - no URL required."""
        logger.info("ContinuousMove called")
        
        if request.HasField('pan_tilt'):
            logger.info(f"Demo: Continuous move pan: {request.pan_tilt.position.x}, tilt: {request.pan_tilt.position.y}")
        
        if request.HasField('zoom'):
            logger.info(f"Demo: Continuous zoom: {request.zoom.position.x}")
        
        if request.timeout > 0:
            logger.info(f"Demo: Movement timeout: {request.timeout} seconds")
        
        return onvif_pb2.ContinuousMoveResponse(
            success=True,
            message="Demo: Continuous move command simulated successfully"
        )

    def Stop(self, request, context):
        """Simulate stopping PTZ movement - no URL required."""
        logger.info("Stop called")
        
        if request.pan_tilt:
            logger.info("Demo: Stopping pan/tilt movement")
        
        if request.zoom:
            logger.info("Demo: Stopping zoom movement")
        
        return onvif_pb2.StopResponse(
            success=True,
            message="Demo: Stop command simulated successfully"
        )

    def GetPresets(self, request, context):
        """Return hardcoded presets - no URL required."""
        logger.info("GetPresets called")
        
        presets = []
        for preset_data in self.demo_presets:
            preset = onvif_pb2.Preset(
                token=preset_data['token'],
                name=preset_data['name']
            )
            
            # Set pan/tilt position
            preset.pan_tilt.position.x = preset_data['pan_tilt']['x']
            preset.pan_tilt.position.y = preset_data['pan_tilt']['y']
            
            # Set zoom position
            preset.zoom.position.x = preset_data['zoom']['x']
            
            presets.append(preset)
        
        return onvif_pb2.GetPresetsResponse(presets=presets)

    def GotoPreset(self, request, context):
        """Simulate going to a preset position - no URL required."""
        logger.info(f"GotoPreset called for preset: {request.preset_token}")
        
        # Find the preset
        preset_found = False
        for preset_data in self.demo_presets:
            if preset_data['token'] == request.preset_token:
                preset_found = True
                logger.info(f"Demo: Moving to preset: {preset_data['name']}")
                logger.info(f"Demo: Target position - Pan: {preset_data['pan_tilt']['x']}, Tilt: {preset_data['pan_tilt']['y']}, Zoom: {preset_data['zoom']['x']}")
                break
        
        if not preset_found:
            logger.warning(f"Demo: Preset token not found: {request.preset_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Preset token not found")
            return onvif_pb2.GotoPresetResponse(
                success=False,
                message="Demo: Preset token not found"
            )
        
        return onvif_pb2.GotoPresetResponse(
            success=True,
            message="Demo: Goto preset command simulated successfully"
        )

    def SetPreset(self, request, context):
        """Simulate setting a preset - no URL required."""
        logger.info(f"SetPreset called with name: {request.preset_name}")
        
        # Generate a new preset token
        new_token = f"Preset_{len(self.demo_presets) + 1}"
        
        # Add to demo presets (in a real implementation, this would be persistent)
        new_preset = {
            'token': new_token,
            'name': request.preset_name or f"Preset_{len(self.demo_presets) + 1}",
            'pan_tilt': {'x': 0.0, 'y': 0.0},  # Current position would be used in real implementation
            'zoom': {'x': 0.0}
        }
        self.demo_presets.append(new_preset)
        
        logger.info(f"Demo: Created new preset: {new_preset['name']} with token: {new_token}")
        
        return onvif_pb2.SetPresetResponse(
            success=True,
            message="Demo: Preset set successfully",
            preset_token=new_token
        )

    def CreatePreset(self, request, context):
        """Simulate creating a preset with optional position - no URL required."""
        logger.info("CreatePreset called")
        
        # Generate a new preset token
        new_token = f"Preset_{len(self.demo_presets) + 1}"
        
        # Use provided position or default to center
        pan_tilt = {'x': 0.0, 'y': 0.0}
        zoom = {'x': 0.0}
        
        if request.HasField('pan_tilt'):
            pan_tilt = {'x': request.pan_tilt.position.x, 'y': request.pan_tilt.position.y}
            logger.info(f"Demo: Creating preset at pan: {pan_tilt['x']}, tilt: {pan_tilt['y']}")
        
        if request.HasField('zoom'):
            zoom = {'x': request.zoom.position.x}
            logger.info(f"Demo: Creating preset at zoom: {zoom['x']}")
        
        # Add to demo presets
        new_preset = {
            'token': new_token,
            'name': f"Auto_Preset_{len(self.demo_presets) + 1}",
            'pan_tilt': pan_tilt,
            'zoom': zoom
        }
        self.demo_presets.append(new_preset)
        
        logger.info(f"Demo: Created new preset: {new_preset['name']} with token: {new_token}")
        
        return onvif_pb2.CreatePresetResponse(
            success=True,
            message="Demo: Preset created successfully",
            preset_token=new_token
        )

    def RemovePreset(self, request, context):
        """Simulate removing a preset - no URL required."""
        logger.info(f"RemovePreset called for preset: {request.preset_token}")
        
        # Find and remove the preset
        preset_found = False
        for i, preset_data in enumerate(self.demo_presets):
            if preset_data['token'] == request.preset_token:
                removed_preset = self.demo_presets.pop(i)
                preset_found = True
                logger.info(f"Demo: Removed preset: {removed_preset['name']}")
                break
        
        if not preset_found:
            logger.warning(f"Demo: Preset token not found for removal: {request.preset_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Preset token not found")
            return onvif_pb2.RemovePresetResponse(
                success=False,
                message="Demo: Preset token not found"
            )
        
        return onvif_pb2.RemovePresetResponse(
            success=True,
            message="Demo: Preset removed successfully"
        )