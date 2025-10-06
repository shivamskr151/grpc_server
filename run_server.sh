#!/bin/bash

# Exit on any error
set -e

# Always run from the script's directory so relative paths work
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -----------------------------
# 1. Set environment variables
# -----------------------------
export GRPC_PYTHON_BUILD_WITH_CYTHON=0
export MACOSX_DEPLOYMENT_TARGET=13.0   # adjust to your macOS version
export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1

# -----------------------------
# 2. Create & activate venv
# -----------------------------
PYTHON_BIN="$(command -v python3 || true)"
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ python3 not found. Please install Python 3."
    exit 1
fi

RECREATE_VENV=false
if [ ! -d "venv" ]; then
    RECREATE_VENV=true
else
    # If layout file missing, mark for recreation
    if [ ! -f "venv/bin/activate" ]; then
        RECREATE_VENV=true
    fi
    # If venv python not executable or cannot run, mark for recreation
    if [ -x "venv/bin/python" ]; then
        if ! "venv/bin/python" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
            RECREATE_VENV=true
        fi
    else
        RECREATE_VENV=true
    fi
    # If pip shebang points to a non-existent interpreter, mark for recreation
    if [ -f "venv/bin/pip" ]; then
        PIP_SHEBANG_INTERP="$(head -n1 venv/bin/pip | sed -e 's/^#!\s*//')"
        if [ -n "$PIP_SHEBANG_INTERP" ] && [ ! -x "$PIP_SHEBANG_INTERP" ]; then
            RECREATE_VENV=true
        fi
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    echo "♻️  Creating fresh virtual environment..."
    rm -rf venv
    "$PYTHON_BIN" -m venv venv
    echo "✅ Virtual environment created."
fi

source venv/bin/activate

# Use the venv's python explicitly
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"

# -----------------------------
# 3. Upgrade pip, setuptools, wheel
# -----------------------------
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1 "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

# -----------------------------
# 4. Install requirements with pre-built wheels
# -----------------------------
PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1 "$VENV_PYTHON" -m pip install --prefer-binary -r requirements.txt

# -----------------------------
# 4b. Resolve and export ONVIF WSDL directory
# -----------------------------
ONVIF_WSDL_DIR="$("$VENV_PYTHON" - <<'PY'
try:
    import pathlib
    import importlib
    wsdl = importlib.import_module('wsdl')
    print(pathlib.Path(wsdl.__file__).parent)
except Exception:
    print("")
PY
)"
if [ -n "$ONVIF_WSDL_DIR" ] && [ -d "$ONVIF_WSDL_DIR" ]; then
    export ONVIF_WSDL_DIR
fi

# -----------------------------
# 5. Generate gRPC Python files
# -----------------------------
"$VENV_PYTHON" -m grpc_tools.protoc -I./proto --python_out=./proto --grpc_python_out=./proto ./proto/onvif.proto
echo "✅ gRPC Python files generated."

# -----------------------------
# 6. Start gRPC server
# -----------------------------
exec "$VENV_PYTHON" grpc_server.py
