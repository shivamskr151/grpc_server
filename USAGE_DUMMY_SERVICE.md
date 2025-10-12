# Dummy ONVIF Service V2 - Usage Guide

## Overview

This guide explains how to use the **Dummy ONVIF Service V2** and test script. These tools allow you to develop and test ONVIF gRPC applications **without requiring a real camera**.

## Files Created

1. **`services/dummy_onvif_service_v2.py`** - Mock ONVIF service with in-memory storage
2. **`test_all_grpc_services.py`** - Comprehensive test script for all 18 gRPC methods

## Features

### Dummy Service Features
- ✅ **No Real Camera Required** - All data stored in memory
- ✅ **All 18 gRPC Methods Implemented** - Complete ONVIF functionality
- ✅ **Persistent State** - Camera state maintained during session
- ✅ **Multiple Device Support** - Handle multiple virtual cameras
- ✅ **Preset Tour Execution** - Background thread-based tour execution
- ✅ **Default Test Data** - Pre-populated with 3 presets

### Test Script Features
- ✅ **Comprehensive Testing** - Tests all 18 gRPC service methods
- ✅ **Colored Output** - Easy-to-read results with ANSI colors
- ✅ **Detailed Reporting** - Shows success/failure for each test
- ✅ **Statistics Summary** - Overall pass/fail rate
- ✅ **Connection Testing** - Verifies server availability

## Quick Start

### 1. Start the Dummy Service

```bash
# Method 1: Run directly
python -m services.dummy_onvif_service_v2

# Method 2: Run in background
nohup python -m services.dummy_onvif_service_v2 > /tmp/dummy_onvif.log 2>&1 &
```

You should see:
```
INFO:__main__:Dummy ONVIF Service V2 initialized with in-memory storage
INFO:__main__:🚀 Dummy ONVIF Service V2 started on port 50051
INFO:__main__:📝 No real camera required - all operations use in-memory data
```

### 2. Run the Test Script

```bash
# Run all tests
python test_all_grpc_services.py

# Run with custom server address
python test_all_grpc_services.py --server localhost:50051
```

### 3. Expected Output

```
================================================================================
                 ONVIF gRPC Service - Comprehensive Test Suite                  
================================================================================

✓ Connected to gRPC server at localhost:50051

Running 18 tests...

[1/18] Testing: GetDeviceInformation
  Manufacturer: Dummy ONVIF Camera
  Model: Mock PTZ Camera V2
  ...
✓ GetDeviceInformation - PASSED

...

Statistics:
  Total Tests:  18
  Passed:       18
  Failed:       0

🎉 ALL TESTS PASSED! 🎉
```

## Service Methods Tested

### Device Information (4 methods)
1. **GetDeviceInformation** - Get camera manufacturer, model, firmware, etc.
2. **GetCapabilities** - Check PTZ, imaging, media, events support
3. **GetProfiles** - Get available media profiles
4. **GetStreamUri** - Get RTSP stream URI

### PTZ Movement (5 methods)
5. **AbsoluteMove** - Move to absolute pan/tilt/zoom position
6. **RelativeMove** - Move relative to current position
7. **ContinuousMove** - Start continuous movement
8. **Stop** - Stop PTZ movement
9. **GetPTZStatus** - Get current PTZ position and status

### Preset Management (5 methods)
10. **GetPresets** - List all saved presets
11. **SetPreset** - Save current position as preset
12. **GotoPreset** - Move to saved preset
13. **CreatePreset** - Create preset at specified position
14. **RemovePreset** - Delete a preset

### Preset Tours (4 methods)
15. **CreatePresetTour** - Create new patrol tour
16. **GetPresetTours** - List all tours
17. **ModifyPresetTour** - Update existing tour
18. **OperatePresetTour** - Start/stop/pause/resume tour

## Default Test Data

The dummy service comes pre-configured with:

### Default Presets
- **preset_1**: Home Position (0.0, 0.0, 0.0)
- **preset_2**: Entrance View (0.5, 0.2, 0.3)
- **preset_3**: Parking View (-0.3, -0.1, 0.5)

### Camera Information
- **Manufacturer**: Dummy ONVIF Camera
- **Model**: Mock PTZ Camera V2
- **Firmware**: 2.0.0
- **Serial Number**: Auto-generated (SN-0001, SN-0002, etc.)

## Using the Dummy Service in Your Code

```python
import grpc
from proto import onvif_v2_pb2 as onvif_pb2
from proto import onvif_v2_pb2_grpc as onvif_pb2_grpc

# Connect to dummy service
channel = grpc.insecure_channel('localhost:50051')
stub = onvif_pb2_grpc.OnvifServiceStub(channel)

# Example: Get device information
request = onvif_pb2.GetDeviceInformationRequest(
    device_url="http://192.168.1.100",
    username="admin",
    password="password"
)
response = stub.GetDeviceInformation(request)
print(f"Camera: {response.manufacturer} {response.model}")

# Example: Move camera
pan_tilt = onvif_pb2.PanTilt()
pan_tilt.position.x = 0.5
pan_tilt.position.y = 0.3
pan_tilt.speed.x = 0.5
pan_tilt.speed.y = 0.5

request = onvif_pb2.AbsoluteMoveRequest(
    device_url="http://192.168.1.100",
    username="admin",
    password="password",
    pan_tilt=pan_tilt
)
response = stub.AbsoluteMove(request)
print(f"Move result: {response.message}")

# Example: Create and start preset tour
steps = [
    onvif_pb2.TourStep(preset_token="preset_1", speed=0.5, wait_time=5),
    onvif_pb2.TourStep(preset_token="preset_2", speed=0.5, wait_time=5),
    onvif_pb2.TourStep(preset_token="preset_3", speed=0.5, wait_time=5)
]

create_req = onvif_pb2.CreatePresetTourRequest(
    device_url="http://192.168.1.100",
    username="admin",
    password="password",
    tour_name="My Patrol",
    steps=steps
)
create_resp = stub.CreatePresetTour(create_req)
print(f"Tour created: {create_resp.tour_token}")

# Start the tour
operate_req = onvif_pb2.OperatePresetTourRequest(
    device_url="http://192.168.1.100",
    username="admin",
    password="password",
    tour_token=create_resp.tour_token,
    operation="start"
)
operate_resp = stub.OperatePresetTour(operate_req)
print(f"Tour started: {operate_resp.message}")
```

## Advanced Features

### Multiple Virtual Cameras

The dummy service can handle multiple virtual cameras simultaneously. Each unique combination of `device_url` and `username` creates a separate virtual camera with its own state:

```python
# Camera 1
request1 = onvif_pb2.GetDeviceInformationRequest(
    device_url="http://192.168.1.100",
    username="admin",
    password="pass123"
)

# Camera 2 (different device_url)
request2 = onvif_pb2.GetDeviceInformationRequest(
    device_url="http://192.168.1.101",
    username="admin",
    password="pass123"
)

# Camera 3 (different username)
request3 = onvif_pb2.GetDeviceInformationRequest(
    device_url="http://192.168.1.100",
    username="user2",
    password="pass123"
)
```

Each camera will have:
- Independent PTZ position
- Separate preset list
- Individual preset tours
- Unique serial numbers

### Background Tour Execution

When you start a preset tour using `OperatePresetTour` with operation="start", the dummy service:
1. Creates a background thread
2. Loops through all tour steps
3. Moves to each preset in sequence
4. Waits at each position for the specified time
5. Repeats the tour until stopped

You can monitor tour execution in the logs:

```
INFO:__main__:Tour execution started: My Patrol
INFO:__main__:Tour 'My Patrol': Moving to preset 'Home Position'
INFO:__main__:Tour 'My Patrol': Waiting 5s at preset 'Home Position'
...
```

## Troubleshooting

### Port Already in Use

If you see `Address already in use`, stop any running services:

```bash
# Find process using port 50051
lsof -i :50051

# Kill the process
kill <PID>
```

### Connection Refused

Ensure the dummy service is running:

```bash
# Check if service is running
lsof -i :50051

# Check logs if running in background
cat /tmp/dummy_onvif.log
```

### Import Errors

Ensure proto files are generated:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/onvif_v2.proto
```

## Comparison with Real Service

| Feature | Dummy Service | Real Service (onvif_service_v2.py) |
|---------|---------------|-----------------------------------|
| Real Camera Required | ❌ No | ✅ Yes |
| WSDL Files Required | ❌ No | ✅ Yes |
| Network Connection | ❌ No | ✅ Yes |
| Instant Response | ✅ Yes | ⏱️ Network dependent |
| State Persistence | 💾 In-memory only | 💾 Camera hardware |
| Perfect for Testing | ✅ Yes | ❌ No |
| Production Ready | ❌ No | ✅ Yes |

## Best Practices

1. **Development**: Use dummy service for initial development and testing
2. **Integration Testing**: Use dummy service in CI/CD pipelines
3. **Unit Tests**: Mock service responses in unit tests
4. **Staging**: Use real service with test cameras
5. **Production**: Always use real service (onvif_service_v2.py)

## Next Steps

1. **Develop Your Client** - Use the dummy service to build your client application
2. **Run Tests Frequently** - Verify your changes don't break existing functionality
3. **Switch to Real Service** - Test with actual cameras before production
4. **Monitor Performance** - Check response times and error rates

## Support

For issues or questions:
- Check the service logs
- Run the test script to verify service health
- Review proto definitions in `proto/onvif_v2.proto`
- Compare with real service implementation in `services/onvif_service_v2.py`

---

**Happy Testing! 🎉**

