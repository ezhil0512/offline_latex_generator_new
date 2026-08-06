import os
import yaml
from typing import Any, Dict

class Config:
    """Configuration loader skeleton for Offline LaTeX Generator."""
    def __init__(self):
        self._config_data: Dict[str, Any] = {}
        self.env = os.getenv("OLG_ENV", "development")
        self.load_config()

    def load_config(self) -> None:
        """Loads configuration files with environment overrides.
        Note: Actual logic is skeleton only.
        """
        # In a real setup, we would load config/default.yaml,
        # then config/{env}.yaml, and override with environment variables.
        # This skeleton simply sets up basic accessors.
        self._config_data = {
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "max_upload_size_mb": 50,
                "allowed_extensions": ["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "tif"]
            },
            "workspace": {
                "root": os.getenv("WORKSPACE_ROOT"),
                "ttl_minutes": 30,
                "cleanup_interval_seconds": 60
            },
            "logging": {
                "level": "DEBUG" if self.env == "development" else "INFO",
                "format": "text" if self.env == "development" else "json"
            },
            "debug": {
                "enabled": self.env == "development"
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a config value by dot-notation key (e.g. 'server.port')."""
        parts = key.split(".")
        val = self._config_data
        for part in parts:
            if isinstance(val, dict) and part in val:
                val = val[part]
            else:
                return default
        return val

# Global configuration instance
config = Config()
