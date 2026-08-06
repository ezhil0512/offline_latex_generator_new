import os
import yaml
from pathlib import Path
from typing import Any, Dict

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges dict2 into dict1."""
    for key, val in dict2.items():
        if isinstance(val, dict) and key in dict1 and isinstance(dict1[key], dict):
            deep_merge(dict1[key], val)
        else:
            dict1[key] = val
    return dict1

class Config:
    """Configuration loader for Offline LaTeX Generator."""
    def __init__(self):
        self._config_data: Dict[str, Any] = {}
        self.env = os.getenv("OLG_ENV", "development")
        self.load_config()

    def load_config(self) -> None:
        """Loads configuration files with environment overrides using pathlib.Path."""
        project_root = Path(__file__).resolve().parents[2]
        
        # Load default config
        default_path = project_root / "config" / "default.yaml"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                self._config_data = yaml.safe_load(f) or {}
        else:
            self._config_data = {}

        # Merge environment config
        env_path = project_root / "config" / f"{self.env}.yaml"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                env_data = yaml.safe_load(f) or {}
                self._config_data = deep_merge(self._config_data, env_data)

        # Merge environment overrides
        workspace_root = os.getenv("WORKSPACE_ROOT")
        if workspace_root:
            if "workspace" not in self._config_data:
                self._config_data["workspace"] = {}
            self._config_data["workspace"]["root"] = workspace_root

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a config value by dot-notation key (e.g. 'server.port')."""
        if key == "workspace.root":
            env_val = os.getenv("WORKSPACE_ROOT")
            if env_val:
                return env_val

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

