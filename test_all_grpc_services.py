#!/usr/bin/env python3
"""
Test All ONVIF gRPC Services
=============================
Comprehensive test script for all 18 gRPC service methods.
Tests the dummy service without requiring a real camera.

Usage:
    python test_all_grpc_services.py
"""

import sys
import time
import grpc
import os

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'proto'))

from proto import onvif_v2_pb2 as onvif_pb2
from proto import onvif_v2_pb2_grpc as onvif_pb2_grpc


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}\n")


def print_test(test_name, step_num, total_steps):
    """Print test name."""
    print(f"{Colors.BOLD}{Colors.BLUE}[{step_num}/{total_steps}] Testing: {test_name}{Colors.END}")


def print_success(message):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message):
    """Print info message."""
    print(f"{Colors.YELLOW}  {message}{Colors.END}")


class ONVIFServiceTester:
    """Test all ONVIF gRPC service methods."""

    def __init__(self, server_address='localhost:50051'):
        """Initialize the tester with server address."""
        self.server_address = server_address
        self.channel = None
        self.stub = None
        
        # Test data
        self.device_url = "http://192.168.1.100"
        self.username = "admin"
        self.password = "password123"
        
        # Results tracking
        self.total_tests = 18
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    def connect(self):
        """Connect to the gRPC server."""
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = onvif_pb2_grpc.OnvifServiceStub(self.channel)
            
            # Test connection
            grpc.channel_ready_future(self.channel).result(timeout=5)
            print_success(f"Connected to gRPC server at {self.server_address}")
            return True
        except Exception as e:
            print_error(f"Failed to connect to server: {e}")
            return False

    def disconnect(self):
        """Disconnect from the gRPC server."""
        if self.channel:
            self.channel.close()
            print_success("Disconnected from gRPC server")

    def run_test(self, test_name, test_func, step_num):
        """Run a single test and track results."""
        print_test(test_name, step_num, self.total_tests)
        try:
            result = test_func()
            if result:
                self.passed_tests += 1
                self.test_results.append((test_name, "PASS", None))
                print_success(f"{test_name} - PASSED\n")
            else:
                self.failed_tests += 1
                self.test_results.append((test_name, "FAIL", "Test returned False"))
                print_error(f"{test_name} - FAILED\n")
            return result
        except Exception as e:
            self.failed_tests += 1
            self.test_results.append((test_name, "FAIL", str(e)))
            print_error(f"{test_name} - FAILED: {e}\n")
            return False

    # ========================================================================
    # Test Methods for Device Information
    # ========================================================================

    def test_get_device_information(self):
        """Test GetDeviceInformation."""
        request = onvif_pb2.GetDeviceInformationRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetDeviceInformation(request)
        
        print_info(f"Manufacturer: {response.manufacturer}")
        print_info(f"Model: {response.model}")
        print_info(f"Firmware: {response.firmware_version}")
        print_info(f"Serial Number: {response.serial_number}")
        print_info(f"Hardware ID: {response.hardware_id}")
        
        return bool(response.manufacturer and response.model)

    def test_get_capabilities(self):
        """Test GetCapabilities."""
        request = onvif_pb2.GetCapabilitiesRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetCapabilities(request)
        
        print_info(f"PTZ Support: {response.ptz_support}")
        print_info(f"Imaging Support: {response.imaging_support}")
        print_info(f"Media Support: {response.media_support}")
        print_info(f"Events Support: {response.events_support}")
        print_info(f"PTZ Preset Tour Support: {response.ptz_preset_tour_support}")
        
        return response.ptz_support and response.media_support

    def test_get_profiles(self):
        """Test GetProfiles."""
        request = onvif_pb2.GetProfilesRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetProfiles(request)
        
        print_info(f"Number of profiles: {len(response.profiles)}")
        for profile in response.profiles:
            print_info(f"  - {profile.name} (token: {profile.token})")
        
        return len(response.profiles) > 0

    def test_get_stream_uri(self):
        """Test GetStreamUri."""
        request = onvif_pb2.GetStreamUriRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            stream_type="RTP-Unicast"
        )
        response = self.stub.GetStreamUri(request)
        
        print_info(f"Stream URI: {response.uri}")
        print_info(f"Timeout: {response.timeout}")
        
        return bool(response.uri)

    # ========================================================================
    # Test Methods for PTZ Movement
    # ========================================================================

    def test_absolute_move(self):
        """Test AbsoluteMove."""
        pan_tilt = onvif_pb2.PanTilt()
        pan_tilt.position.x = 0.3
        pan_tilt.position.y = 0.2
        pan_tilt.speed.x = 0.5
        pan_tilt.speed.y = 0.5
        
        zoom = onvif_pb2.Zoom()
        zoom.position.x = 0.4
        zoom.speed.x = 0.5
        
        request = onvif_pb2.AbsoluteMoveRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            pan_tilt=pan_tilt,
            zoom=zoom
        )
        response = self.stub.AbsoluteMove(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_relative_move(self):
        """Test RelativeMove."""
        pan_tilt = onvif_pb2.PanTilt()
        pan_tilt.position.x = 0.1
        pan_tilt.position.y = 0.1
        pan_tilt.speed.x = 0.5
        pan_tilt.speed.y = 0.5
        
        request = onvif_pb2.RelativeMoveRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            pan_tilt=pan_tilt
        )
        response = self.stub.RelativeMove(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_continuous_move(self):
        """Test ContinuousMove."""
        pan_tilt = onvif_pb2.PanTilt()
        pan_tilt.position.x = 0.2  # velocity
        pan_tilt.position.y = 0.0
        
        request = onvif_pb2.ContinuousMoveRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            pan_tilt=pan_tilt,
            timeout=2
        )
        response = self.stub.ContinuousMove(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_stop(self):
        """Test Stop."""
        request = onvif_pb2.StopRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            pan_tilt=True,
            zoom=True
        )
        response = self.stub.Stop(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_get_ptz_status(self):
        """Test GetPTZStatus."""
        request = onvif_pb2.GetPTZStatusRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetPTZStatus(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Pan: {response.pan_tilt.position.x}, Tilt: {response.pan_tilt.position.y}")
        print_info(f"Zoom: {response.zoom.position.x}")
        print_info(f"Moving: {response.moving}")
        
        return response.success

    # ========================================================================
    # Test Methods for Presets
    # ========================================================================

    def test_get_presets(self):
        """Test GetPresets."""
        request = onvif_pb2.GetPresetsRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetPresets(request)
        
        print_info(f"Number of presets: {len(response.presets)}")
        for preset in response.presets:
            print_info(f"  - {preset.name} (token: {preset.token})")
        
        return len(response.presets) > 0

    def test_set_preset(self):
        """Test SetPreset."""
        request = onvif_pb2.SetPresetRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            preset_name="Test Preset"
        )
        response = self.stub.SetPreset(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        print_info(f"Preset Token: {response.preset_token}")
        
        # Store preset token for later tests
        if response.success and response.preset_token:
            self.test_preset_token = response.preset_token
        
        return response.success

    def test_goto_preset(self):
        """Test GotoPreset."""
        # Use the first default preset
        request = onvif_pb2.GotoPresetRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            preset_token="preset_1"
        )
        response = self.stub.GotoPreset(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_create_preset(self):
        """Test CreatePreset."""
        pan_tilt = onvif_pb2.PanTilt()
        pan_tilt.position.x = 0.5
        pan_tilt.position.y = 0.3
        pan_tilt.speed.x = 0.5
        pan_tilt.speed.y = 0.5
        
        zoom = onvif_pb2.Zoom()
        zoom.position.x = 0.6
        zoom.speed.x = 0.5
        
        request = onvif_pb2.CreatePresetRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            pan_tilt=pan_tilt,
            zoom=zoom
        )
        response = self.stub.CreatePreset(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        print_info(f"Preset Token: {response.preset_token}")
        
        # Store for removal test
        if response.success and response.preset_token:
            self.created_preset_token = response.preset_token
        
        return response.success

    def test_remove_preset(self):
        """Test RemovePreset."""
        # Use the preset we created earlier
        preset_token = getattr(self, 'created_preset_token', 'preset_1')
        
        request = onvif_pb2.RemovePresetRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            preset_token=preset_token
        )
        response = self.stub.RemovePreset(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    # ========================================================================
    # Test Methods for Preset Tours
    # ========================================================================

    def test_create_preset_tour(self):
        """Test CreatePresetTour."""
        # Create tour steps
        steps = []
        for i in range(1, 4):
            step = onvif_pb2.TourStep(
                preset_token=f"preset_{i}",
                speed=0.5,
                wait_time=3
            )
            steps.append(step)
        
        # Create starting condition
        condition = onvif_pb2.StartingCondition(
            recurring_time=10,
            recurring_duration="PT10S",
            random_preset_order=False
        )
        
        request = onvif_pb2.CreatePresetTourRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            tour_name="Test Tour",
            steps=steps,
            auto_start=False,
            starting_condition=condition
        )
        response = self.stub.CreatePresetTour(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        print_info(f"Tour Token: {response.tour_token}")
        
        # Store for later tests
        if response.success and response.tour_token:
            self.tour_token = response.tour_token
        
        return response.success

    def test_get_preset_tours(self):
        """Test GetPresetTours."""
        request = onvif_pb2.GetPresetToursRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password
        )
        response = self.stub.GetPresetTours(request)
        
        print_info(f"Number of tours: {len(response.tours)}")
        for tour in response.tours:
            print_info(f"  - {tour.name} (token: {tour.token}, steps: {len(tour.steps)}, running: {tour.is_running})")
        
        return len(response.tours) > 0

    def test_modify_preset_tour(self):
        """Test ModifyPresetTour."""
        tour_token = getattr(self, 'tour_token', 'tour_1')
        
        # Create modified steps
        steps = []
        for i in range(1, 3):
            step = onvif_pb2.TourStep(
                preset_token=f"preset_{i}",
                speed=0.7,
                wait_time=5
            )
            steps.append(step)
        
        request = onvif_pb2.ModifyPresetTourRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            tour_token=tour_token,
            steps=steps,
            auto_start=True
        )
        response = self.stub.ModifyPresetTour(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    def test_operate_preset_tour_start(self):
        """Test OperatePresetTour - Start."""
        tour_token = getattr(self, 'tour_token', 'tour_1')
        
        request = onvif_pb2.OperatePresetTourRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            tour_token=tour_token,
            operation="start"
        )
        response = self.stub.OperatePresetTour(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        # Wait a bit for tour to run
        if response.success:
            print_info("Waiting 3 seconds for tour to run...")
            time.sleep(3)
        
        return response.success

    def test_operate_preset_tour_stop(self):
        """Test OperatePresetTour - Stop."""
        tour_token = getattr(self, 'tour_token', 'tour_1')
        
        request = onvif_pb2.OperatePresetTourRequest(
            device_url=self.device_url,
            username=self.username,
            password=self.password,
            tour_token=tour_token,
            operation="stop"
        )
        response = self.stub.OperatePresetTour(request)
        
        print_info(f"Success: {response.success}")
        print_info(f"Message: {response.message}")
        
        return response.success

    # ========================================================================
    # Main Test Runner
    # ========================================================================

    def run_all_tests(self):
        """Run all tests in sequence."""
        print_header("ONVIF gRPC Service - Comprehensive Test Suite")
        
        if not self.connect():
            print_error("Cannot connect to server. Please start the dummy service first.")
            print_info("Run: python -m services.dummy_onvif_service_v2")
            return False
        
        print(f"\n{Colors.BOLD}Running {self.total_tests} tests...{Colors.END}\n")
        
        step = 1
        
        # Device Information Tests
        self.run_test("GetDeviceInformation", self.test_get_device_information, step)
        step += 1
        
        self.run_test("GetCapabilities", self.test_get_capabilities, step)
        step += 1
        
        self.run_test("GetProfiles", self.test_get_profiles, step)
        step += 1
        
        self.run_test("GetStreamUri", self.test_get_stream_uri, step)
        step += 1
        
        # PTZ Movement Tests
        self.run_test("AbsoluteMove", self.test_absolute_move, step)
        step += 1
        
        self.run_test("RelativeMove", self.test_relative_move, step)
        step += 1
        
        self.run_test("ContinuousMove", self.test_continuous_move, step)
        step += 1
        
        self.run_test("Stop", self.test_stop, step)
        step += 1
        
        self.run_test("GetPTZStatus", self.test_get_ptz_status, step)
        step += 1
        
        # Preset Tests
        self.run_test("GetPresets", self.test_get_presets, step)
        step += 1
        
        self.run_test("SetPreset", self.test_set_preset, step)
        step += 1
        
        self.run_test("GotoPreset", self.test_goto_preset, step)
        step += 1
        
        self.run_test("CreatePreset", self.test_create_preset, step)
        step += 1
        
        self.run_test("RemovePreset", self.test_remove_preset, step)
        step += 1
        
        # Preset Tour Tests
        self.run_test("CreatePresetTour", self.test_create_preset_tour, step)
        step += 1
        
        self.run_test("GetPresetTours", self.test_get_preset_tours, step)
        step += 1
        
        self.run_test("ModifyPresetTour", self.test_modify_preset_tour, step)
        step += 1
        
        self.run_test("OperatePresetTour (Start)", self.test_operate_preset_tour_start, step)
        step += 1
        
        self.run_test("OperatePresetTour (Stop)", self.test_operate_preset_tour_stop, step)
        
        # Print summary
        self.print_summary()
        
        self.disconnect()
        
        return self.failed_tests == 0

    def print_summary(self):
        """Print test summary."""
        print_header("Test Results Summary")
        
        # Print detailed results
        for test_name, status, error in self.test_results:
            if status == "PASS":
                print(f"{Colors.GREEN}✓ {test_name:40} PASSED{Colors.END}")
            else:
                print(f"{Colors.RED}✗ {test_name:40} FAILED{Colors.END}")
                if error:
                    print(f"  {Colors.RED}  Error: {error}{Colors.END}")
        
        # Print statistics
        print(f"\n{Colors.BOLD}Statistics:{Colors.END}")
        print(f"  Total Tests:  {self.total_tests}")
        print(f"  {Colors.GREEN}Passed:       {self.passed_tests}{Colors.END}")
        print(f"  {Colors.RED}Failed:       {self.failed_tests}{Colors.END}")
        
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        if success_rate == 100:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.END}")
        elif success_rate >= 80:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Most tests passed ({success_rate:.1f}%){Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Many tests failed ({success_rate:.1f}%){Colors.END}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test all ONVIF gRPC services')
    parser.add_argument(
        '--server',
        default='localhost:50051',
        help='gRPC server address (default: localhost:50051)'
    )
    args = parser.parse_args()
    
    tester = ONVIFServiceTester(server_address=args.server)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

