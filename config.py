#!/usr/bin/env python3
"""
Configuration management for ONVIF gRPC Server
Supports YAML, JSON, and environment variable configuration
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Server configuration settings"""
    host: str = "0.0.0.0"
    port: int = 50051
    max_workers: int = 10
    enable_reflection: bool = True
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class OnvifConfig:
    """ONVIF service configuration settings"""
    wsdl_dir: Optional[str] = None
    default_timeout: int = 30
    connection_timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    enabled: bool = False
    host: str = "localhost"
    port: int = 27017
    database: str = "onvif_grpc"
    username: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    enable_tls: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    require_auth: bool = False
    auth_token: Optional[str] = None


@dataclass
class MonitoringConfig:
    """Monitoring and metrics configuration"""
    enable_metrics: bool = False
    metrics_port: int = 9090
    enable_health_check: bool = True
    health_check_interval: int = 30


@dataclass
class AppConfig:
    """Main application configuration"""
    server: ServerConfig = field(default_factory=ServerConfig)
    onvif: OnvifConfig = field(default_factory=OnvifConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Service selection
    service_type: str = "real"  # "demo" or "real"
    
    # Development settings
    debug: bool = False
    reload: bool = False


class ConfigManager:
    """Configuration manager with support for multiple sources"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: AppConfig = AppConfig()
        self._load_config()
    
    def _load_config(self):
        """Load configuration from multiple sources in order of precedence"""
        # 1. Load from config file
        if self.config_path and Path(self.config_path).exists():
            self._load_from_file(self.config_path)
        else:
            # Try default config files
            for default_path in ["config.yaml", "config.yml", "config.json"]:
                if Path(default_path).exists():
                    self._load_from_file(default_path)
                    break
        
        # 2. Override with environment variables
        self._load_from_env()
        
        # 3. Apply any final validations
        self._validate_config()
    
    def _load_from_file(self, file_path: str):
        """Load configuration from YAML or JSON file"""
        try:
            with open(file_path, 'r') as f:
                if file_path.endswith('.json'):
                    config_data = json.load(f)
                else:
                    config_data = yaml.safe_load(f)
            
            self._merge_config(config_data)
            logger.info(f"Configuration loaded from {file_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {file_path}: {e}")
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        env_mappings = {
            # Server settings
            'GRPC_HOST': ('server.host', str),
            'GRPC_PORT': ('server.port', int),
            'GRPC_MAX_WORKERS': ('server.max_workers', int),
            'GRPC_ENABLE_REFLECTION': ('server.enable_reflection', self._str_to_bool),
            'LOG_LEVEL': ('server.log_level', str),
            
            # ONVIF settings
            'ONVIF_WSDL_DIR': ('onvif.wsdl_dir', str),
            'ONVIF_TIMEOUT': ('onvif.default_timeout', int),
            'ONVIF_CONNECTION_TIMEOUT': ('onvif.connection_timeout', int),
            'ONVIF_MAX_RETRIES': ('onvif.max_retries', int),
            'ONVIF_RETRY_DELAY': ('onvif.retry_delay', float),
            'ONVIF_ENABLE_CACHING': ('onvif.enable_caching', self._str_to_bool),
            'ONVIF_CACHE_TTL': ('onvif.cache_ttl', int),
            
            # Database settings
            'DB_ENABLED': ('database.enabled', self._str_to_bool),
            'DB_HOST': ('database.host', str),
            'DB_PORT': ('database.port', int),
            'DB_NAME': ('database.database', str),
            'DB_USERNAME': ('database.username', str),
            'DB_PASSWORD': ('database.password', str),
            'DB_CONNECTION_STRING': ('database.connection_string', str),
            
            # Security settings
            'TLS_ENABLED': ('security.enable_tls', self._str_to_bool),
            'TLS_CERT_FILE': ('security.cert_file', str),
            'TLS_KEY_FILE': ('security.key_file', str),
            'TLS_CA_FILE': ('security.ca_file', str),
            'AUTH_REQUIRED': ('security.require_auth', self._str_to_bool),
            'AUTH_TOKEN': ('security.auth_token', str),
            
            # Monitoring settings
            'METRICS_ENABLED': ('monitoring.enable_metrics', self._str_to_bool),
            'METRICS_PORT': ('monitoring.metrics_port', int),
            'HEALTH_CHECK_ENABLED': ('monitoring.enable_health_check', self._str_to_bool),
            'HEALTH_CHECK_INTERVAL': ('monitoring.health_check_interval', int),
            
            # App settings
            'SERVICE_TYPE': ('service_type', str),
            'DEBUG': ('debug', self._str_to_bool),
            'RELOAD': ('reload', self._str_to_bool),
        }
        
        for env_var, (config_path, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    self._set_nested_config(config_path, converted_value)
                except Exception as e:
                    logger.warning(f"Failed to convert environment variable {env_var}={value}: {e}")
    
    def _merge_config(self, config_data: Dict[str, Any]):
        """Merge configuration data into the config object"""
        if not isinstance(config_data, dict):
            return
        
        # Server config
        if 'server' in config_data:
            server_data = config_data['server']
            if isinstance(server_data, dict):
                for key, value in server_data.items():
                    if hasattr(self.config.server, key):
                        setattr(self.config.server, key, value)
        
        # ONVIF config
        if 'onvif' in config_data:
            onvif_data = config_data['onvif']
            if isinstance(onvif_data, dict):
                for key, value in onvif_data.items():
                    if hasattr(self.config.onvif, key):
                        setattr(self.config.onvif, key, value)
        
        # Database config
        if 'database' in config_data:
            db_data = config_data['database']
            if isinstance(db_data, dict):
                for key, value in db_data.items():
                    if hasattr(self.config.database, key):
                        setattr(self.config.database, key, value)
        
        # Security config
        if 'security' in config_data:
            security_data = config_data['security']
            if isinstance(security_data, dict):
                for key, value in security_data.items():
                    if hasattr(self.config.security, key):
                        setattr(self.config.security, key, value)
        
        # Monitoring config
        if 'monitoring' in config_data:
            monitoring_data = config_data['monitoring']
            if isinstance(monitoring_data, dict):
                for key, value in monitoring_data.items():
                    if hasattr(self.config.monitoring, key):
                        setattr(self.config.monitoring, key, value)
        
        # Top-level settings
        for key in ['service_type', 'debug', 'reload']:
            if key in config_data:
                setattr(self.config, key, config_data[key])
    
    def _set_nested_config(self, path: str, value: Any):
        """Set a nested configuration value using dot notation"""
        parts = path.split('.')
        if len(parts) == 2:
            section, key = parts
            if section == 'server' and hasattr(self.config.server, key):
                setattr(self.config.server, key, value)
            elif section == 'onvif' and hasattr(self.config.onvif, key):
                setattr(self.config.onvif, key, value)
            elif section == 'database' and hasattr(self.config.database, key):
                setattr(self.config.database, key, value)
            elif section == 'security' and hasattr(self.config.security, key):
                setattr(self.config.security, key, value)
            elif section == 'monitoring' and hasattr(self.config.monitoring, key):
                setattr(self.config.monitoring, key, value)
        elif len(parts) == 1:
            key = parts[0]
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def _str_to_bool(self, value: str) -> bool:
        """Convert string to boolean"""
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    def _validate_config(self):
        """Validate configuration values"""
        # Validate port numbers
        if not (1 <= self.config.server.port <= 65535):
            raise ValueError(f"Invalid server port: {self.config.server.port}")
        
        if not (1 <= self.config.monitoring.metrics_port <= 65535):
            raise ValueError(f"Invalid metrics port: {self.config.monitoring.metrics_port}")
        
        # Validate service type
        if self.config.service_type not in ['demo', 'real']:
            raise ValueError(f"Invalid service type: {self.config.service_type}")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.config.server.log_level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.config.server.log_level}")
        
        # Validate TLS settings
        if self.config.security.enable_tls:
            if not self.config.security.cert_file or not self.config.security.key_file:
                raise ValueError("TLS enabled but cert_file or key_file not specified")
    
    def get_config(self) -> AppConfig:
        """Get the current configuration"""
        return self.config
    
    def save_config(self, file_path: str, format: str = 'yaml'):
        """Save current configuration to file"""
        config_dict = {
            'server': {
                'host': self.config.server.host,
                'port': self.config.server.port,
                'max_workers': self.config.server.max_workers,
                'enable_reflection': self.config.server.enable_reflection,
                'log_level': self.config.server.log_level,
                'log_format': self.config.server.log_format,
            },
            'onvif': {
                'wsdl_dir': self.config.onvif.wsdl_dir,
                'default_timeout': self.config.onvif.default_timeout,
                'connection_timeout': self.config.onvif.connection_timeout,
                'max_retries': self.config.onvif.max_retries,
                'retry_delay': self.config.onvif.retry_delay,
                'enable_caching': self.config.onvif.enable_caching,
                'cache_ttl': self.config.onvif.cache_ttl,
            },
            'database': {
                'enabled': self.config.database.enabled,
                'host': self.config.database.host,
                'port': self.config.database.port,
                'database': self.config.database.database,
                'username': self.config.database.username,
                'password': self.config.database.password,
                'connection_string': self.config.database.connection_string,
            },
            'security': {
                'enable_tls': self.config.security.enable_tls,
                'cert_file': self.config.security.cert_file,
                'key_file': self.config.security.key_file,
                'ca_file': self.config.security.ca_file,
                'require_auth': self.config.security.require_auth,
                'auth_token': self.config.security.auth_token,
            },
            'monitoring': {
                'enable_metrics': self.config.monitoring.enable_metrics,
                'metrics_port': self.config.monitoring.metrics_port,
                'enable_health_check': self.config.monitoring.enable_health_check,
                'health_check_interval': self.config.monitoring.health_check_interval,
            },
            'service_type': self.config.service_type,
            'debug': self.config.debug,
            'reload': self.config.reload,
        }
        
        try:
            with open(file_path, 'w') as f:
                if format.lower() == 'json':
                    json.dump(config_dict, f, indent=2)
                else:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {e}")
            raise


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Get or create the global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config() -> AppConfig:
    """Get the current application configuration"""
    return get_config_manager().get_config()


def reload_config(config_path: Optional[str] = None):
    """Reload configuration from file and environment"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
