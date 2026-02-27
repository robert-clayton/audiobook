"""YAML configuration loader and saver for the audiobook pipeline."""

import yaml


def load_config(path):
    """Load and parse a YAML config file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed configuration as a dict.
    """
    with open(path) as f:
        return yaml.safe_load(f)


def save_config(path, cfg):
    """Write a configuration dict back to a YAML file.

    Args:
        path: Destination YAML file path.
        cfg: Configuration dict to serialize.
    """
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False)
