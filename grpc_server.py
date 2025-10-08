#!/usr/bin/env python3
"""
ONVIF gRPC Server
Provides ONVIF camera control functionality via gRPC
"""

import grpc
from concurrent import futures
import logging
import sys
import os
import signal

# Add the current directory and the proto directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'proto'))

from proto import onvif_pb2_grpc
from proto import onvif_pb2
from services.demo_onvif_service import DemoOnvifService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def serve():
    """Start the gRPC server with reflection and graceful shutdown."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Register demo service
    onvif_service = DemoOnvifService()
    onvif_pb2_grpc.add_OnvifServiceServicer_to_server(onvif_service, server)

    # Enable server reflection for grpcurl/grpcui usage
    try:
        from grpc_reflection.v1alpha import reflection
        service_names = (
            onvif_pb2.DESCRIPTOR.services_by_name['OnvifService'].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(service_names, server)
        logger.info("gRPC reflection enabled")
    except Exception as e:
        logger.warning(f"gRPC reflection not available: {e}")

    # Bind port (env override supported)
    port = os.getenv('GRPC_PORT', '50051')
    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    # Start server
    server.start()
    logger.info(f"gRPC server started on {listen_addr} (DemoOnvifService)")

    # Graceful shutdown on SIGTERM/SIGINT
    def handle_signal(signum, frame):
        logger.info("Shutting down server...")
        server.stop(0)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    server.wait_for_termination()

if __name__ == '__main__':
    serve()
