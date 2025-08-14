import yaml
from typing import Dict, Any
from pathlib import Path


def load_config(path: str | Path) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        path: Path to the configuration file

    Returns:
        Dictionary containing the configuration

    Raises:
        FileNotFoundError: If the config file doesn't exist
        yaml.YAMLError: If the YAML is malformed
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(path: str | Path, cfg: Dict[str, Any]) -> None:
    """
    Save configuration to a YAML file.

    Args:
        path: Path to save the configuration file
        cfg: Configuration dictionary to save
    """
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)
