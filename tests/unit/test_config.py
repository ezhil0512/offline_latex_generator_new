import os
from pathlib import Path
from offline_latex_generator.config import Config, deep_merge

def test_deep_merge():
    dict1 = {"a": 1, "b": {"c": 2, "d": 3}}
    dict2 = {"b": {"d": 4, "e": 5}, "f": 6}
    merged = deep_merge(dict1, dict2)
    assert merged["a"] == 1
    assert merged["b"]["c"] == 2
    assert merged["b"]["d"] == 4
    assert merged["b"]["e"] == 5
    assert merged["f"] == 6

def test_default_config_loading():
    config = Config()
    assert config.get("server.port") == 5000
    assert config.get("server.host") == "0.0.0.0"
    assert config.get("workspace.ttl_minutes") in [15, 30] # depends on environment

def test_env_specific_config_loading(monkeypatch):
    monkeypatch.setenv("OLG_ENV", "production")
    config = Config()
    assert config.env == "production"
    assert config.get("workspace.ttl_minutes") == 15
    assert config.get("logging.level") == "WARNING"

def test_workspace_root_env_override(monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", "/custom/path/to/workspace")
    config = Config()
    assert config.get("workspace.root") == "/custom/path/to/workspace"
