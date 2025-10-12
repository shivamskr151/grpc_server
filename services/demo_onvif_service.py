#!/usr/bin/env python3
"""
Demo ONVIF Service - Complete ONVIF Camera Simulation
Simulates a full ONVIF PTZ camera with presets, tours, and all functionality
"""

import logging
import threading
import time
import random
from typing import Dict, List, Optional, Any
import grpc

from proto import onvif_pb2
from proto import onvif_pb2_grpc

logger = logging.getLogger(__name__)

class DemoOnvifService(onvif_pb2_grpc.OnvifServiceServicer):
    """Complete ONVIF camera simulation with PTZ, presets, and tours."""

    def __init__(self):
        # Camera state
        self.camera_state = {
            'pan': 0.0,
            'tilt': 0.0,
            'zoom': 0.0,
            'is_moving': False,
            'last_movement': time.time()
        }
        
        # Camera capabilities
        self.capabilities = {
            'ptz_support': True,
            'imaging_support': True,
            'media_support': True,
            'events_support': True,
            'ptz_preset_tour_support': True
        }
        
        # Camera profiles
        self.profiles = [
            {
                'token': 'Profile_1',
                'name': 'Main Stream',
                'resolution': '1920x1080',
                'fps': 30,
                'ptz_enabled': True
            },
            {
                'token': 'Profile_2', 
                'name': 'Sub Stream',
                'resolution': '640x480',
                'fps': 15,
                'ptz_enabled': True
            }
        ]
        
        # Preset storage
        self.presets = [
            {
                'token': 'Preset_1',
                'name': 'Home Position',
                'pan': 0.0,
                'tilt': 0.0,
                'zoom': 0.0,
                'created_at': time.time()
            },
            {
                'token': 'Preset_2',
                'name': 'Left Corner',
                'pan': -1.0,
                'tilt': 0.5,
                'zoom': 0.2,
                'created_at': time.time()
            },
            {
                'token': 'Preset_3',
                'name': 'Right Corner',
                'pan': 1.0,
                'tilt': 0.5,
                'zoom': 0.2,
                'created_at': time.time()
            }
        ]
        
        # Preset tour storage
        self.preset_tours = [
            {
                'token': 'Tour_1',
                'name': 'SecurityPatrol',
                'steps': [
                    {'preset_token': 'Preset_1', 'speed': 0.5, 'wait_time': 3},
                    {'preset_token': 'Preset_2', 'speed': 0.6, 'wait_time': 4},
                    {'preset_token': 'Preset_3', 'speed': 0.7, 'wait_time': 5}
                ],
                'is_running': False,
                'manual_loop_thread': None,
                'stop_manual_loop': False,
                'auto_start': True,
                'starting_condition': {
                    'recurring_time': 0,  # infinite loop
                    'recurring_duration': 'PT10S',  # 10 sec gap before restarting
                    'random_preset_order': False
                },
                'created_at': time.time()
            }
        ]
        
        # Manual loop execution control
        self.manual_loop_lock = threading.Lock()
        
        # Movement simulation
        self.movement_thread = None
        self.movement_target = None
        self.movement_speed = 0.0
        
        logger.info("Demo ONVIF Service initialized - Complete camera simulation with PTZ, presets, and tours")

    def _simulate_movement(self, target_pan: float, target_tilt: float, target_zoom: float, speed: float = 1.0):
        """Simulate smooth camera movement to target position."""
        if self.movement_thread and self.movement_thread.is_alive():
            return  # Already moving
        
        self.movement_target = {'pan': target_pan, 'tilt': target_tilt, 'zoom': target_zoom}
        self.movement_speed = speed
        self.camera_state['is_moving'] = True
        
        def move():
            start_time = time.time()
            start_pan = self.camera_state['pan']
            start_tilt = self.camera_state['tilt']
            start_zoom = self.camera_state['zoom']
            
            # Calculate movement duration based on distance and speed
            pan_distance = abs(target_pan - start_pan)
            tilt_distance = abs(target_tilt - start_tilt)
            zoom_distance = abs(target_zoom - start_zoom)
            max_distance = max(pan_distance, tilt_distance, zoom_distance)
            
            # Movement duration (faster with higher speed)
            duration = max_distance / (speed * 2.0)  # Base speed of 2 units per second
            
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time
                progress = min(elapsed / duration, 1.0)
                
                # Smooth interpolation
                self.camera_state['pan'] = start_pan + (target_pan - start_pan) * progress
                self.camera_state['tilt'] = start_tilt + (target_tilt - start_tilt) * progress
                self.camera_state['zoom'] = start_zoom + (target_zoom - start_zoom) * progress
                
                time.sleep(0.1)  # Update every 100ms
            
            # Ensure exact target position
            self.camera_state['pan'] = target_pan
            self.camera_state['tilt'] = target_tilt
            self.camera_state['zoom'] = target_zoom
            self.camera_state['is_moving'] = False
            self.camera_state['last_movement'] = time.time()
        
        self.movement_thread = threading.Thread(target=move, daemon=True)
        self.movement_thread.start()

    def _execute_manual_loop(self, tour_data: Dict[str, Any]):
        """Execute manual loop for cameras that don't support native patrol."""
        logger.info(f"Starting manual loop for tour: {tour_data['name']}")
        
        try:
            while not tour_data['stop_manual_loop']:
                steps = tour_data['steps'].copy()
                
                # Randomize order if configured
                if tour_data['starting_condition']['random_preset_order']:
                    random.shuffle(steps)
                
                for step in steps:
                    if tour_data['stop_manual_loop']:
                        break
                    
                    # Find preset
                    preset = None
                    for p in self.presets:
                        if p['token'] == step['preset_token']:
                            preset = p
                            break
                    
                    if not preset:
                        logger.warning(f"Preset not found: {step['preset_token']}")
                        continue
                    
                    # Execute movement
                    logger.info(f"Manual loop - Moving to preset: {preset['name']} at speed: {step['speed']}")
                    self._simulate_movement(
                        preset['pan'], 
                        preset['tilt'], 
                        preset['zoom'], 
                        step['speed']
                    )
                    
                    # Wait for movement to complete
                    while self.camera_state['is_moving']:
                        time.sleep(0.1)
                    
                    # Wait for the specified time
                    wait_time = step['wait_time']
                    logger.info(f"Manual loop - Waiting {wait_time} seconds at preset: {preset['name']}")
                    
                    # Check for stop signal during wait
                    for _ in range(wait_time):
                        if tour_data['stop_manual_loop']:
                            logger.info(f"Manual loop stopped during wait at preset: {preset['name']}")
                            return
                        time.sleep(1)
                        
        except Exception as e:
            logger.error(f"Error in manual loop execution: {e}")
        finally:
            logger.info(f"Manual loop completed for tour: {tour_data['name']}")

    def _resolve_profile_token(self, requested_token: Optional[str] = None) -> str:
        """Resolve profile token to a valid profile."""
        if not requested_token:
            return self.profiles[0]['token']
        
        for profile in self.profiles:
            if profile['token'] == requested_token:
                return requested_token
        
        # If not found, return first profile
        return self.profiles[0]['token']

    def _get_profile_token_safely(self, request) -> Optional[str]:
        """Safely get profile_token from request."""
        try:
            if hasattr(request, 'HasField') and request.HasField('profile_token'):
                return request.profile_token
            else:
                return None
        except Exception:
            return None

    # ========================
    # Device Information
    # ========================

    def GetDeviceInformation(self, request, context):
        """Return simulated device information."""
        logger.info("GetDeviceInformation called")
        return onvif_pb2.GetDeviceInformationResponse(
            manufacturer="Demo Camera Corp",
            model="PTZ-Demo-2024",
            firmware_version="1.0.0",
            serial_number="DEMO-12345",
            hardware_id="DEMO-HW-001"
        )

    def GetCapabilities(self, request, context):
        """Return camera capabilities."""
        logger.info("GetCapabilities called")
        return onvif_pb2.GetCapabilitiesResponse(
            ptz_support=self.capabilities['ptz_support'],
            imaging_support=self.capabilities['imaging_support'],
            media_support=self.capabilities['media_support'],
            events_support=self.capabilities['events_support'],
            ptz_preset_tour_support=self.capabilities['ptz_preset_tour_support']
        )

    def GetProfiles(self, request, context):
        """Return available camera profiles."""
        logger.info("GetProfiles called")
        profiles = []
        for profile in self.profiles:
            profiles.append(onvif_pb2.Profile(
                token=profile['token'],
                name=profile['name']
            ))
        return onvif_pb2.GetProfilesResponse(profiles=profiles)

    def GetStreamUri(self, request, context):
        """Return stream URI for the profile."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"GetStreamUri called for profile: {profile_token}")
        
        # Find profile
        profile = None
        for p in self.profiles:
            if p['token'] == profile_token:
                profile = p
                break
        
        if not profile:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Profile not found")
            return onvif_pb2.GetStreamUriResponse()
        
        # Generate stream URI based on profile
        if profile['token'] == 'Profile_1':
            stream_uri = "rtsp://demo-camera.local:554/main_stream"
        else:
            stream_uri = "rtsp://demo-camera.local:554/sub_stream"
        
        return onvif_pb2.GetStreamUriResponse(uri=stream_uri, timeout="PT60S")

    # ========================
    # PTZ Control
    # ========================

    def AbsoluteMove(self, request, context):
        """Move camera to absolute position."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        
        # Extract pan, tilt, zoom from protobuf structure
        pan = request.pan_tilt.position.x if request.HasField('pan_tilt') and request.pan_tilt.HasField('position') else 0.0
        tilt = request.pan_tilt.position.y if request.HasField('pan_tilt') and request.pan_tilt.HasField('position') else 0.0
        zoom = request.zoom.position.x if request.HasField('zoom') and request.zoom.HasField('position') else 0.0
        
        logger.info(f"AbsoluteMove called - Pan: {pan}, Tilt: {tilt}, Zoom: {zoom}")
        
        # Simulate movement
        self._simulate_movement(pan, tilt, zoom, 1.0)
        
        return onvif_pb2.AbsoluteMoveResponse(success=True, message="Movement started")

    def RelativeMove(self, request, context):
        """Move camera relative to current position."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        
        # Extract pan, tilt, zoom from protobuf structure
        pan_delta = request.pan_tilt.position.x if request.HasField('pan_tilt') and request.pan_tilt.HasField('position') else 0.0
        tilt_delta = request.pan_tilt.position.y if request.HasField('pan_tilt') and request.pan_tilt.HasField('position') else 0.0
        zoom_delta = request.zoom.position.x if request.HasField('zoom') and request.zoom.HasField('position') else 0.0
        
        logger.info(f"RelativeMove called - Pan: {pan_delta}, Tilt: {tilt_delta}, Zoom: {zoom_delta}")
        
        # Calculate new position
        new_pan = self.camera_state['pan'] + pan_delta
        new_tilt = self.camera_state['tilt'] + tilt_delta
        new_zoom = self.camera_state['zoom'] + zoom_delta
        
        # Clamp values to valid range
        new_pan = max(-1.0, min(1.0, new_pan))
        new_tilt = max(-1.0, min(1.0, new_tilt))
        new_zoom = max(0.0, min(1.0, new_zoom))
        
        # Simulate movement
        self._simulate_movement(new_pan, new_tilt, new_zoom, 1.0)
        
        return onvif_pb2.RelativeMoveResponse(success=True, message="Relative movement started")

    def ContinuousMove(self, request, context):
        """Start continuous camera movement."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        
        # Extract pan, tilt, zoom from protobuf structure
        pan_speed = request.pan_tilt.speed.x if request.HasField('pan_tilt') and request.pan_tilt.HasField('speed') else 0.0
        tilt_speed = request.pan_tilt.speed.y if request.HasField('pan_tilt') and request.pan_tilt.HasField('speed') else 0.0
        zoom_speed = request.zoom.speed.x if request.HasField('zoom') and request.zoom.HasField('speed') else 0.0
        
        logger.info(f"ContinuousMove called - Pan: {pan_speed}, Tilt: {tilt_speed}, Zoom: {zoom_speed}")
        
        # For demo, we'll simulate continuous movement for a short time
        def continuous_move():
            duration = 2.0  # Move for 2 seconds
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Update position based on speed
                self.camera_state['pan'] += pan_speed * 0.1
                self.camera_state['tilt'] += tilt_speed * 0.1
                self.camera_state['zoom'] += zoom_speed * 0.1
                
                # Clamp values
                self.camera_state['pan'] = max(-1.0, min(1.0, self.camera_state['pan']))
                self.camera_state['tilt'] = max(-1.0, min(1.0, self.camera_state['tilt']))
                self.camera_state['zoom'] = max(0.0, min(1.0, self.camera_state['zoom']))
                
                time.sleep(0.1)
        
        threading.Thread(target=continuous_move, daemon=True).start()
        
        return onvif_pb2.ContinuousMoveResponse(success=True, message="Continuous movement started")

    def Stop(self, request, context):
        """Stop camera movement."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info("Stop called")
        
        self.camera_state['is_moving'] = False
        if self.movement_thread and self.movement_thread.is_alive():
            # Wait for movement to complete
            self.movement_thread.join(timeout=1.0)
        
        return onvif_pb2.StopResponse(success=True, message="Movement stopped")

    def GetPTZStatus(self, request, context):
        """Get current PTZ status and position."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"GetPTZStatus called for profile: {profile_token}")
        
        # Create the response with proper field setting
        response = onvif_pb2.GetPTZStatusResponse()
        response.success = True
        response.message = "PTZ status retrieved"
        response.pan_tilt.position.x = self.camera_state['pan']
        response.pan_tilt.position.y = self.camera_state['tilt']
        response.zoom.position.x = self.camera_state['zoom']
        response.moving = self.camera_state['is_moving']
        return response

    # ========================
    # Preset Management
    # ========================

    def GetPresets(self, request, context):
        """Return all available presets."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"GetPresets called for profile: {profile_token}")
        
        presets = []
        for preset in self.presets:
            presets.append(onvif_pb2.Preset(
                token=preset['token'],
                name=preset['name']
            ))
        
        return onvif_pb2.GetPresetsResponse(presets=presets)

    def GotoPreset(self, request, context):
        """Move camera to a specific preset."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"GotoPreset called for preset: {request.preset_token}")
        
        # Find preset
        preset = None
        for p in self.presets:
            if p['token'] == request.preset_token:
                preset = p
                break
        
        if not preset:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Preset not found")
            return onvif_pb2.GotoPresetResponse(success=False, message="Preset not found")
        
        # Simulate movement to preset position
        logger.info(f"Moving to preset: {preset['name']}")
        logger.info(f"Target position - Pan: {preset['pan']}, Tilt: {preset['tilt']}, Zoom: {preset['zoom']}")
        
        self._simulate_movement(preset['pan'], preset['tilt'], preset['zoom'], 1.0)
        
        return onvif_pb2.GotoPresetResponse(success=True, message=f"Moved to preset: {preset['name']}")

    def SetPreset(self, request, context):
        """Create a new preset at current camera position."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"SetPreset called with name: {request.preset_name}")
        
        # Generate new preset token
        new_token = f"Preset_{len(self.presets) + 1}"
        
        # Create new preset
        new_preset = {
            'token': new_token,
            'name': request.preset_name or f"Preset_{len(self.presets) + 1}",
            'pan': self.camera_state['pan'],
            'tilt': self.camera_state['tilt'],
            'zoom': self.camera_state['zoom'],
            'created_at': time.time()
        }
        
        self.presets.append(new_preset)
        
        logger.info(f"Created new preset: {new_preset['name']} at position - Pan: {new_preset['pan']}, Tilt: {new_preset['tilt']}, Zoom: {new_preset['zoom']}")
        
        return onvif_pb2.SetPresetResponse(
            success=True,
            message=f"Preset '{new_preset['name']}' created successfully",
            preset_token=new_token
        )

    def CreatePreset(self, request, context):
        """Create a new preset with optional position."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"CreatePreset called with name: {request.preset_name}")
        
        # Generate new preset token
        new_token = f"Preset_{len(self.presets) + 1}"
        
        # Use provided position or current position
        if hasattr(request, 'pan') and hasattr(request, 'tilt') and hasattr(request, 'zoom'):
            pan = request.pan
            tilt = request.tilt
            zoom = request.zoom
        else:
            pan = self.camera_state['pan']
            tilt = self.camera_state['tilt']
            zoom = self.camera_state['zoom']
        
        # Create new preset
        new_preset = {
            'token': new_token,
            'name': request.preset_name or f"Preset_{len(self.presets) + 1}",
            'pan': pan,
            'tilt': tilt,
            'zoom': zoom,
            'created_at': time.time()
        }
        
        self.presets.append(new_preset)
        
        logger.info(f"Created new preset: {new_preset['name']} at position - Pan: {new_preset['pan']}, Tilt: {new_preset['tilt']}, Zoom: {new_preset['zoom']}")
        
        return onvif_pb2.CreatePresetResponse(
            success=True,
            message=f"Preset '{new_preset['name']}' created successfully",
            preset_token=new_token
        )

    def RemovePreset(self, request, context):
        """Remove a preset."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"RemovePreset called for preset: {request.preset_token}")
        
        # Find and remove preset
        for i, preset in enumerate(self.presets):
            if preset['token'] == request.preset_token:
                removed_preset = self.presets.pop(i)
                logger.info(f"Removed preset: {removed_preset['name']}")
                return onvif_pb2.RemovePresetResponse(
                    success=True,
                    message=f"Preset '{removed_preset['name']}' removed successfully"
                )
        
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Preset not found")
        return onvif_pb2.RemovePresetResponse(success=False, message="Preset not found")

    # ========================
    # PTZ Patrol/Preset Tour
    # ========================
    
    def GetPresetTours(self, request, context):
        """Return all available preset tours."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"GetPresetTours called for profile: {profile_token}")
        
        tours = []
        for tour_data in self.preset_tours:
            tour = onvif_pb2.PresetTour(
                token=tour_data['token'],
                name=tour_data['name'],
                is_running=tour_data['is_running'],
                auto_start=tour_data.get('auto_start', False)
            )
            
            # Add starting condition
            if 'starting_condition' in tour_data:
                condition = onvif_pb2.StartingCondition(
                    recurring_time=tour_data['starting_condition']['recurring_time'],
                    recurring_duration=tour_data['starting_condition']['recurring_duration'],
                    random_preset_order=tour_data['starting_condition']['random_preset_order']
                )
                tour.starting_condition.CopyFrom(condition)
            
            # Add tour steps
            for step_data in tour_data['steps']:
                step = onvif_pb2.TourStep(
                    preset_token=step_data['preset_token'],
                    speed=step_data['speed'],
                    wait_time=step_data['wait_time']
                )
                tour.steps.append(step)
            
            tours.append(tour)
        
        logger.info(f"Demo: Returning {len(tours)} preset tours")
        return onvif_pb2.GetPresetToursResponse(tours=tours)

    def CreatePresetTour(self, request, context):
        """Create a new preset tour."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"CreatePresetTour called with name: {request.tour_name} and profile: {profile_token}")
        
        # Generate a new tour token
        new_token = f"Tour_{len(self.preset_tours) + 1}"
        
        # Create new tour
        new_tour = {
            'token': new_token,
            'name': request.tour_name or f"Tour_{len(self.preset_tours) + 1}",
            'steps': [],  # Empty initially, will be populated by ModifyPresetTour
            'is_running': False,
            'manual_loop_thread': None,
            'stop_manual_loop': False,
            'auto_start': request.auto_start if hasattr(request, 'auto_start') else False,
            'starting_condition': {
                'recurring_time': request.starting_condition.recurring_time if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 0,
                'recurring_duration': request.starting_condition.recurring_duration if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 'PT10S',
                'random_preset_order': request.starting_condition.random_preset_order if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else False
            },
            'created_at': time.time()
        }
        self.preset_tours.append(new_tour)
        
        logger.info(f"Demo: Created new preset tour: {new_tour['name']} with token: {new_token}")
        
        return onvif_pb2.CreatePresetTourResponse(
            success=True,
            message="Demo: Preset tour created successfully",
            tour_token=new_token
        )

    def ModifyPresetTour(self, request, context):
        """Modify a preset tour with new steps."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"ModifyPresetTour called for tour: {request.tour_token} with profile: {profile_token}")
        
        # Find the tour
        tour_found = False
        for tour_data in self.preset_tours:
            if tour_data['token'] == request.tour_token:
                tour_found = True
                
                # Update the steps
                tour_data['steps'] = []
                for step in request.steps:
                    step_data = {
                        'preset_token': step.preset_token,
                        'speed': step.speed,
                        'wait_time': step.wait_time
                    }
                    tour_data['steps'].append(step_data)
                    logger.info(f"Demo: Added step - Preset: {step.preset_token}, Speed: {step.speed}, Wait: {step.wait_time}s")
                
                # Update auto_start and starting_condition if provided
                if hasattr(request, 'auto_start'):
                    tour_data['auto_start'] = request.auto_start
                
                if hasattr(request, 'starting_condition') and request.HasField('starting_condition'):
                    tour_data['starting_condition'] = {
                        'recurring_time': request.starting_condition.recurring_time,
                        'recurring_duration': request.starting_condition.recurring_duration,
                        'random_preset_order': request.starting_condition.random_preset_order
                    }
                break
        
        if not tour_found:
            logger.warning(f"Demo: Tour token not found: {request.tour_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Tour token not found")
            return onvif_pb2.ModifyPresetTourResponse(
                success=False,
                message="Demo: Tour token not found"
            )
        
        return onvif_pb2.ModifyPresetTourResponse(
            success=True,
            message="Demo: Preset tour modified successfully"
        )

    def OperatePresetTour(self, request, context):
        """Operate a preset tour (start/stop/pause/resume)."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"OperatePresetTour called for tour: {request.tour_token} with operation: {request.operation} and profile: {profile_token}")
        
        # Find the tour
        tour_found = False
        for tour_data in self.preset_tours:
            if tour_data['token'] == request.tour_token:
                tour_found = True
                
                if request.operation.lower() == "start":
                    if tour_data['is_running']:
                        logger.info(f"Demo: Tour {tour_data['name']} is already running")
                        return onvif_pb2.OperatePresetTourResponse(
                            success=False,
                            message="Demo: Tour is already running"
                        )
                    
                    tour_data['is_running'] = True
                    tour_data['stop_manual_loop'] = False
                    
                    # Start manual loop
                    logger.info(f"Demo: Started native patrol tour: {tour_data['name']}")
                    logger.info(f"Demo: Tour will cycle through {len(tour_data['steps'])} presets")
                    
                    for i, step in enumerate(tour_data['steps']):
                        logger.info(f"Demo: Step {i+1}: Preset {step['preset_token']}, Speed {step['speed']}, Wait {step['wait_time']}s")
                    
                    # Start manual loop thread
                    tour_data['manual_loop_thread'] = threading.Thread(
                        target=self._execute_manual_loop,
                        args=(tour_data,),
                        daemon=True
                    )
                    tour_data['manual_loop_thread'].start()
                    
                elif request.operation.lower() == "stop":
                    if not tour_data['is_running']:
                        logger.info(f"Demo: Tour {tour_data['name']} is not running")
                        return onvif_pb2.OperatePresetTourResponse(
                            success=False,
                            message="Demo: Tour is not running"
                        )
                    
                    tour_data['is_running'] = False
                    tour_data['stop_manual_loop'] = True
                    logger.info(f"Demo: Stopped tour: {tour_data['name']}")
                    
                    # Wait for manual loop thread to finish
                    if tour_data['manual_loop_thread'] and tour_data['manual_loop_thread'].is_alive():
                        tour_data['manual_loop_thread'].join(timeout=5)
                    
                elif request.operation.lower() in ["pause", "resume"]:
                    logger.info(f"Demo: {request.operation.capitalize()}d tour: {tour_data['name']}")
                    
                else:
                    logger.warning(f"Demo: Unknown tour operation: {request.operation}")
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Invalid operation")
                    return onvif_pb2.OperatePresetTourResponse(
                        success=False,
                        message="Demo: Invalid tour operation"
                    )
                break
        
        if not tour_found:
            logger.warning(f"Demo: Tour token not found: {request.tour_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Tour token not found")
            return onvif_pb2.OperatePresetTourResponse(
                success=False,
                message="Demo: Tour token not found"
            )
        
        return onvif_pb2.OperatePresetTourResponse(
            success=True,
            message=f"Demo: Tour operation '{request.operation}' completed successfully"
        )

    # ========================
    # Native ONVIF Preset Tour API
    # ========================
    
    def CreateNativePresetTour(self, request, context):
        """Create a native ONVIF preset tour (demo simulation)."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"CreateNativePresetTour called with name: {request.tour_name} and profile: {profile_token}")
        
        # Generate a new tour token
        new_token = f"NativeTour_{len(self.preset_tours) + 1}"
        
        # Create new tour with native ONVIF structure
        new_tour = {
            'token': new_token,
            'name': request.tour_name or f"NativeTour_{len(self.preset_tours) + 1}",
            'steps': [],
            'is_running': False,
            'manual_loop_thread': None,
            'stop_manual_loop': False,
            'auto_start': request.auto_start if hasattr(request, 'auto_start') else False,
            'starting_condition': {
                'recurring_time': request.starting_condition.recurring_time if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 0,
                'recurring_duration': request.starting_condition.recurring_duration if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else 'PT10S',
                'random_preset_order': request.starting_condition.random_preset_order if hasattr(request, 'starting_condition') and request.HasField('starting_condition') else False
            },
            'native_onvif': True,  # Mark as native ONVIF tour
            'created_at': time.time()
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
        
        self.preset_tours.append(new_tour)
        
        logger.info(f"Demo: Created native ONVIF preset tour: {new_tour['name']} with token: {new_token}")
        logger.info(f"Demo: AutoStart: {new_tour['auto_start']}, RecurringTime: {new_tour['starting_condition']['recurring_time']}")
        
        return onvif_pb2.CreateNativePresetTourResponse(
            success=True,
            message="Demo: Native ONVIF preset tour created successfully",
            tour_token=new_token
        )

    def ModifyNativePresetTour(self, request, context):
        """Modify a native ONVIF preset tour (demo simulation)."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"ModifyNativePresetTour called for tour: {request.tour_token} with profile: {profile_token}")
        
        # Find the tour
        tour_found = False
        for tour_data in self.preset_tours:
            if tour_data['token'] == request.tour_token:
                tour_found = True
                
                # Update the steps
                if hasattr(request, 'steps') and request.steps:
                    tour_data['steps'] = []
                    for step in request.steps:
                        step_data = {
                            'preset_token': step.preset_token,
                            'speed': step.speed,
                            'wait_time': step.wait_time
                        }
                        tour_data['steps'].append(step_data)
                        logger.info(f"Demo: Native tour - Added step - Preset: {step.preset_token}, Speed: {step.speed}, Wait: {step.wait_time}s")
                
                # Update auto_start and starting_condition
                if hasattr(request, 'auto_start'):
                    tour_data['auto_start'] = request.auto_start
                
                if hasattr(request, 'starting_condition') and request.HasField('starting_condition'):
                    tour_data['starting_condition'] = {
                        'recurring_time': request.starting_condition.recurring_time,
                        'recurring_duration': request.starting_condition.recurring_duration,
                        'random_preset_order': request.starting_condition.random_preset_order
                    }
                    logger.info(f"Demo: Native tour - Updated starting condition: RecurringTime={tour_data['starting_condition']['recurring_time']}, Duration={tour_data['starting_condition']['recurring_duration']}")
                
                break
        
        if not tour_found:
            logger.warning(f"Demo: Native tour token not found: {request.tour_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Tour token not found")
            return onvif_pb2.ModifyNativePresetTourResponse(
                success=False,
                message="Demo: Native tour token not found"
            )
        
        return onvif_pb2.ModifyNativePresetTourResponse(
            success=True,
            message="Demo: Native ONVIF preset tour modified successfully"
        )

    def OperateNativePresetTour(self, request, context):
        """Operate a native ONVIF preset tour (demo simulation)."""
        profile_token = self._resolve_profile_token(self._get_profile_token_safely(request))
        logger.info(f"OperateNativePresetTour called for tour: {request.tour_token} with operation: {request.operation} and profile: {profile_token}")
        
        # Find the tour
        tour_found = False
        for tour_data in self.preset_tours:
            if tour_data['token'] == request.tour_token:
                tour_found = True
                
                if request.operation.lower() == "start":
                    if tour_data['is_running']:
                        logger.info(f"Demo: Native tour {tour_data['name']} is already running")
                        return onvif_pb2.OperateNativePresetTourResponse(
                            success=False,
                            message="Demo: Native tour is already running"
                        )
                    
                    tour_data['is_running'] = True
                    tour_data['stop_manual_loop'] = False
                    
                    # Simulate native ONVIF preset tour
                    logger.info(f"Demo: Started native ONVIF preset tour: {tour_data['name']}")
                    logger.info(f"Demo: Native tour - AutoStart: {tour_data['auto_start']}")
                    logger.info(f"Demo: Native tour - RecurringTime: {tour_data['starting_condition']['recurring_time']}")
                    logger.info(f"Demo: Native tour - RecurringDuration: {tour_data['starting_condition']['recurring_duration']}")
                    logger.info(f"Demo: Native tour - RandomOrder: {tour_data['starting_condition']['random_preset_order']}")
                    logger.info(f"Demo: Native tour will cycle through {len(tour_data['steps'])} presets")
                    
                    for i, step in enumerate(tour_data['steps']):
                        logger.info(f"Demo: Native tour - Step {i+1}: Preset {step['preset_token']}, Speed {step['speed']}, Wait {step['wait_time']}s")
                    
                    # Start manual loop thread for simulation
                    tour_data['manual_loop_thread'] = threading.Thread(
                        target=self._execute_manual_loop,
                        args=(tour_data,),
                        daemon=True
                    )
                    tour_data['manual_loop_thread'].start()
                    
                elif request.operation.lower() == "stop":
                    if not tour_data['is_running']:
                        logger.info(f"Demo: Native tour {tour_data['name']} is not running")
                        return onvif_pb2.OperateNativePresetTourResponse(
                            success=False,
                            message="Demo: Native tour is not running"
                        )
                    
                    tour_data['is_running'] = False
                    tour_data['stop_manual_loop'] = True
                    logger.info(f"Demo: Stopped native ONVIF preset tour: {tour_data['name']}")
                    
                    # Wait for manual loop thread to finish
                    if tour_data['manual_loop_thread'] and tour_data['manual_loop_thread'].is_alive():
                        tour_data['manual_loop_thread'].join(timeout=5)
                    
                elif request.operation.lower() in ["pause", "resume"]:
                    logger.info(f"Demo: {request.operation.capitalize()}d native tour: {tour_data['name']}")
                    
                else:
                    logger.warning(f"Demo: Unknown native tour operation: {request.operation}")
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Invalid operation")
                    return onvif_pb2.OperateNativePresetTourResponse(
                        success=False,
                        message="Demo: Invalid native tour operation"
                    )
                break
        
        if not tour_found:
            logger.warning(f"Demo: Native tour token not found: {request.tour_token}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Tour token not found")
            return onvif_pb2.OperateNativePresetTourResponse(
                success=False,
                message="Demo: Native tour token not found"
            )
        
        return onvif_pb2.OperateNativePresetTourResponse(
            success=True,
            message=f"Demo: Native tour operation '{request.operation}' completed successfully"
        )