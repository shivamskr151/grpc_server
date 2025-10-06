# ONVIF Camera Control System

End-to-end ONVIF camera control with a NestJS REST API that talks to a Python gRPC server. Supports device info, media profiles, stream URIs, PTZ (absolute/relative/continuous/stop), and presets.

### Contents
- Quick start
- Project structure
- Running with Docker
- Local development (manual)
- Configuration
- API endpoints and examples
- Regenerating gRPC stubs
- Troubleshooting and notes

## Quick start

Option A — Docker (recommended):
```bash
cd /Users/shivamkumar/Desktop/cmm-ovif
docker compose up --build
```
Then:
- REST API: http://localhost:3000
- Python gRPC server: localhost:50051

Option B — Manual (two terminals):
1) gRPC server
```bash
cd grpc_server
pip install -r requirements.txt
./run_server.sh    # or: python grpc_server.py
```
2) NestJS client
```bash
cd nestjs_client
npm install
npm run start:dev
```

## Project structure

```
cmm-ovif/
├── docker-compose.yml
├── nestjs_client/          # NestJS REST API acting as a gRPC client
│   ├── src/
│   │   ├── main.ts
│   │   ├── app.module.ts
│   │   ├── grpc/
│   │   │   ├── grpc.module.ts
│   │   │   ├── grpc.service.ts
│   │   │   └── proto/onvif.proto
│   │   ├── controllers/onvif.controller.ts
│   │   └── dtos/ptz.dto.ts
│   ├── package.json
│   └── tsconfig.json
└── grpc_server/            # Python gRPC Server
    ├── proto/
    │   ├── onvif.proto
    │   ├── onvif_pb2.py
    │   └── onvif_pb2_grpc.py
    ├── services/
    │   └── onvif_service.py
    ├── grpc_server.py
    ├── requirements.txt
    └── run_server.sh
```

## Folder structure

Top-level:
- `docker-compose.yml` — Orchestrates NestJS and Python gRPC services
- `nestjs_client/` — NestJS REST API and gRPC client code
- `grpc_server/` — Python gRPC server that talks to ONVIF cameras

NestJS (`nestjs_client/`):
- `src/main.ts` — App bootstrap
- `src/app.module.ts` — Root module
- `src/grpc/grpc.module.ts` — gRPC client configuration (host/port, proto path)
- `src/grpc/grpc.service.ts` — Service wrapping gRPC calls
- `src/grpc/proto/onvif.proto` — Shared service definitions used by the client
- `src/controllers/onvif.controller.ts` — REST endpoints for device, PTZ, presets
- `src/dtos/ptz.dto.ts` — DTOs and validation for PTZ endpoints
- `package.json`, `tsconfig.json` — Dependencies and TS config

Python gRPC (`grpc_server/`):
- `grpc_server.py` — Entry point starting the gRPC server on port 50051
- `proto/onvif.proto` — Source proto definition
- `proto/onvif_pb2.py`, `proto/onvif_pb2_grpc.py` — Generated Python stubs
- `services/onvif_service.py` — Implementation of gRPC methods using ONVIF
- `requirements.txt` — Python dependencies
- `run_server.sh` — Helper script to start server

## Running with Docker

Requirements: Docker Desktop 4+.

```bash
cd /Users/shivamkumar/Desktop/cmm-ovif
docker compose up --build
```

Useful flags:
- Rebuild only on changes: `docker compose up --build --detach`
- Tear down: `docker compose down`

## Local development (manual)

Prerequisites:
- Node.js >= 16
- Python >= 3.8
- ONVIF-compatible camera reachable from your network

gRPC (Python):
```bash
cd grpc_server
pip install -r requirements.txt
python grpc_server.py   # listens on 0.0.0.0:50051
```

NestJS (Node):
```bash
cd nestjs_client
npm install
npm run start:dev       # serves http://localhost:3000
```

## Configuration

- gRPC server host/port: configured in `nestjs_client/src/grpc/grpc.module.ts` (defaults to `localhost:50051`).
- NestJS API port: defaults to `3000` (Nest config).
- Camera credentials are passed per-request in the REST body.

If you need to change the gRPC bind address or port, update `grpc_server/grpc_server.py`.

## API endpoints

Device and media:
- `POST /onvif/device-information` — Get device information
- `POST /onvif/capabilities` — Get device capabilities
- `POST /onvif/profiles` — Get media profiles
- `POST /onvif/stream-uri` — Get stream URI

PTZ:
- `POST /onvif/ptz/absolute-move` — Absolute PTZ positioning
- `POST /onvif/ptz/relative-move` — Relative PTZ movement
- `POST /onvif/ptz/continuous-move` — Continuous PTZ movement
- `POST /onvif/ptz/stop` — Stop PTZ movement

Presets:
- `POST /onvif/ptz/presets` — List PTZ presets
- `POST /onvif/ptz/goto-preset` — Go to preset
- `POST /onvif/ptz/set-preset` — Create/set preset
- `POST /onvif/ptz/remove-preset` — Remove preset

## Examples

Get device information:
```bash
curl -X POST http://localhost:3000/onvif/device-information \
  -H "Content-Type: application/json" \
  -d '{
    "deviceUrl": "http://192.168.1.100:8080",
    "username": "admin",
    "password": "password"
  }'
```

Absolute PTZ move:
```bash
curl -X POST http://localhost:3000/onvif/ptz/absolute-move \
  -H "Content-Type: application/json" \
  -d '{
    "deviceUrl": "http://192.168.1.100:8080",
    "username": "admin",
    "password": "password",
    "profileToken": "Profile_1",
    "panTilt": {
      "position": {"x": 0.5, "y": 0.3},
      "speed": {"x": 0.5, "y": 0.5}
    },
    "zoom": {
      "position": {"x": 0.8},
      "speed": {"x": 0.5}
    }
  }'
```

## Regenerating gRPC stubs (Python)

If you modify `grpc_server/proto/onvif.proto`, regenerate the Python stubs:
```bash
cd grpc_server
python -m grpc_tools.protoc \
  -I proto \
  --python_out=proto \
  --grpc_python_out=proto \
  proto/onvif.proto
```

For NestJS, the client loads the `.proto` directly from `nestjs_client/src/grpc/proto/onvif.proto` at runtime.

## Security notes

- Credentials are sent in request bodies. Consider adding authentication to the NestJS API.
- gRPC is plaintext by default. For production, enable TLS for both gRPC and REST.
- Validate and sanitize all parameters server-side.

## Troubleshooting

1. gRPC connection errors: ensure the Python server is running and reachable on `localhost:50051` (or your configured host).
2. Camera connection failures: verify camera URL, credentials, and that the camera supports ONVIF.
3. Ports busy: check for conflicts on 3000 (REST) and 50051 (gRPC).
4. Dependency issues: re-install deps (`pip install -r grpc_server/requirements.txt`, `npm ci`).

---

Contributions and issues are welcome. If you add methods to the proto, please update the README examples and endpoint list accordingly.
