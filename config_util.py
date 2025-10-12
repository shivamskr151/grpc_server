#!/usr/bin/env python3
"""
Configuration utility for ONVIF gRPC Server
Provides commands to manage configuration files
"""

import argparse
import sys
from pathlib import Path
from config import get_config_manager, get_config


def show_config():
    """Display current configuration"""
    config = get_config()
    
    print("Current Configuration:")
    print("=" * 50)
    
    print(f"Server:")
    print(f"  Host: {config.server.host}")
    print(f"  Port: {config.server.port}")
    print(f"  Max Workers: {config.server.max_workers}")
    print(f"  Enable Reflection: {config.server.enable_reflection}")
    print(f"  Log Level: {config.server.log_level}")
    
    print(f"\nONVIF:")
    print(f"  WSDL Directory: {config.onvif.wsdl_dir or 'Auto-detect'}")
    print(f"  Default Timeout: {config.onvif.default_timeout}s")
    print(f"  Connection Timeout: {config.onvif.connection_timeout}s")
    print(f"  Max Retries: {config.onvif.max_retries}")
    print(f"  Retry Delay: {config.onvif.retry_delay}s")
    print(f"  Enable Caching: {config.onvif.enable_caching}")
    print(f"  Cache TTL: {config.onvif.cache_ttl}s")
    
    print(f"\nDatabase:")
    print(f"  Enabled: {config.database.enabled}")
    if config.database.enabled:
        print(f"  Host: {config.database.host}")
        print(f"  Port: {config.database.port}")
        print(f"  Database: {config.database.database}")
        print(f"  Username: {config.database.username or 'Not set'}")
    
    print(f"\nSecurity:")
    print(f"  Enable TLS: {config.security.enable_tls}")
    if config.security.enable_tls:
        print(f"  Cert File: {config.security.cert_file or 'Not set'}")
        print(f"  Key File: {config.security.key_file or 'Not set'}")
    print(f"  Require Auth: {config.security.require_auth}")
    
    print(f"\nMonitoring:")
    print(f"  Enable Metrics: {config.monitoring.enable_metrics}")
    print(f"  Metrics Port: {config.monitoring.metrics_port}")
    print(f"  Enable Health Check: {config.monitoring.enable_health_check}")
    
    print(f"\nApplication:")
    print(f"  Service Type: {config.service_type}")
    print(f"  Debug: {config.debug}")
    print(f"  Reload: {config.reload}")


def validate_config(config_path=None):
    """Validate configuration file"""
    try:
        if config_path:
            config_manager = get_config_manager(config_path)
        else:
            config_manager = get_config_manager()
        
        config = config_manager.get_config()
        print("✓ Configuration is valid")
        return True
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='ONVIF gRPC Server Configuration Utility')
    parser.add_argument('--config', '-c', type=str, help='Path to configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Show command
    subparsers.add_parser('show', help='Show current configuration')
    
    # Validate command
    subparsers.add_parser('validate', help='Validate configuration')
    
    # Save command
    save_parser = subparsers.add_parser('save', help='Save configuration to file')
    save_parser.add_argument('output', help='Output file path')
    save_parser.add_argument('--format', choices=['yaml', 'json'], default='yaml', 
                           help='Output format')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Load config if specified
    if args.config:
        config_manager = get_config_manager(args.config)
    else:
        config_manager = get_config_manager()
    
    if args.command == 'show':
        show_config()
    elif args.command == 'validate':
        success = validate_config(args.config)
        sys.exit(0 if success else 1)
    elif args.command == 'save':
        try:
            config_manager.save_config(args.output, args.format)
            print(f"Configuration saved to {args.output}")
        except Exception as e:
            print(f"Failed to save configuration: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()

