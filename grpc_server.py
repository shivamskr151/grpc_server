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
import argparse
from pathlib import Path

# Add the current directory and the proto directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'proto'))

# Force reload protobuf modules to ensure latest definitions are loaded
if 'proto.onvif_pb2' in sys.modules:
    del sys.modules['proto.onvif_pb2']
if 'proto.onvif_pb2_grpc' in sys.modules:
    del sys.modules['proto.onvif_pb2_grpc']

from proto import onvif_v2_pb2_grpc as onvif_pb2_grpc
from proto import onvif_v2_pb2 as onvif_pb2
from services.dummy_onvif_service_v2 import DummyOnvifServiceV2
from services.onvif_service_v2 import OnvifService
from config import get_config_manager, get_config

# Load configuration
config_manager = get_config_manager()
config = get_config()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.server.log_level.upper()),
    format=config.server.log_format
)
logger = logging.getLogger(__name__)

def serve():
    """Start the gRPC server with reflection and graceful shutdown."""
    # Create server with configured max workers
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=config.server.max_workers))

    # Register service based on configuration
    if config.service_type == "demo":
        onvif_service = DummyOnvifServiceV2()
        service_name = "DummyOnvifServiceV2"
    else:
        onvif_service = OnvifService()
        service_name = "OnvifService"
    
    onvif_pb2_grpc.add_OnvifServiceServicer_to_server(onvif_service, server)
    logger.info(f"Registered {service_name}")
    
    # Debug: Log available methods
    service_descriptor = onvif_pb2.DESCRIPTOR.services_by_name.get('OnvifService')
    if service_descriptor:
        method_names = [method.name for method in service_descriptor.methods]
        logger.info(f"Available methods: {method_names}")
        
        # Check for PTZ Patrol methods
        patrol_methods = [name for name in method_names if 'PresetTour' in name or 'Patrol' in name]
        if patrol_methods:
            logger.info(f"PTZ Patrol methods found: {patrol_methods}")
        else:
            logger.warning("No PTZ Patrol methods found in service descriptor")

    # Enable server reflection if configured
    if config.server.enable_reflection:
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

    # Bind to configured address and port
    listen_addr = f"{config.server.host}:{config.server.port}"
    
    # Add port based on security configuration
    if config.security.enable_tls:
        if not config.security.cert_file or not config.security.key_file:
            logger.error("TLS enabled but certificate files not configured")
            sys.exit(1)
        
        try:
            with open(config.security.cert_file, 'rb') as f:
                cert_chain = f.read()
            with open(config.security.key_file, 'rb') as f:
                private_key = f.read()
            
            credentials = grpc.ssl_server_credentials([(private_key, cert_chain)])
            server.add_secure_port(listen_addr, credentials)
            logger.info(f"gRPC server configured with TLS on {listen_addr}")
        except Exception as e:
            logger.error(f"Failed to load TLS certificates: {e}")
            sys.exit(1)
    else:
        server.add_insecure_port(listen_addr)
        logger.info(f"gRPC server configured without TLS on {listen_addr}")

    # Start server
    server.start()
    logger.info(f"gRPC server started on {listen_addr} ({service_name})")
    logger.info(f"Configuration: service_type={config.service_type}, debug={config.debug}")

    # Graceful shutdown on SIGTERM/SIGINT
    def handle_signal(signum, frame):
        logger.info("Shutting down server...")
        server.stop(0)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    server.wait_for_termination()

def main():
    """Main entry point with command line argument support."""
    parser = argparse.ArgumentParser(description='ONVIF gRPC Server')
    parser.add_argument('--config', '-c', type=str, help='Path to configuration file')
    parser.add_argument('--service-type', choices=['demo', 'real'], 
                       help='Service type to use (overrides config)')
    parser.add_argument('--port', type=int, help='Server port (overrides config)')
    parser.add_argument('--host', type=str, help='Server host (overrides config)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--save-config', type=str, 
                       help='Save current configuration to file and exit')
    
    args = parser.parse_args()
    
    # Reload config if custom config file specified
    if args.config:
        global config_manager, config
        config_manager = get_config_manager(args.config)
        config = get_config()
    
    # Override config with command line arguments
    if args.service_type:
        config.service_type = args.service_type
    if args.port:
        config.server.port = args.port
    if args.host:
        config.server.host = args.host
    if args.debug:
        config.debug = True
        config.server.log_level = "DEBUG"
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Save config and exit if requested
    if args.save_config:
        config_manager.save_config(args.save_config)
        print(f"Configuration saved to {args.save_config}")
        return
    
    # Start the server
    serve()


if __name__ == '__main__':
    main()
