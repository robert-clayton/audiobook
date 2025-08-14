from typing import Dict, Any, List
from pathlib import Path
import re
from urllib.parse import urlparse


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConfigValidator:
    """Validates audiobook configuration files."""

    REQUIRED_CONFIG_KEYS = ["output_dir"]
    REQUIRED_SERIES_KEYS = ["name", "url", "narrator"]
    VALID_NARRATORS = [
        "alloy",
        "fable",
        "jewel_high",
        "john",
        "katie_low",
        "katie_rant",
        "katie",
        "nova",
        "onyx",
        "robert_low",
        "shimmer",
        "yuuka_low",
        "yuuka",
    ]
    VALID_SYSTEM_TYPES = ["bold", "italic", "bracket", "braces", "table"]

    def __init__(self, speakers_dir: Path = Path("speakers")):
        self.speakers_dir = speakers_dir

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate the entire configuration structure.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ConfigValidationError: If validation fails
        """
        if not isinstance(config, dict):
            raise ConfigValidationError("Configuration must be a dictionary")

        # Validate top-level structure
        if "config" not in config:
            raise ConfigValidationError("Missing 'config' section")
        if "series" not in config:
            raise ConfigValidationError("Missing 'series' section")

        # Validate config section
        self._validate_config_section(config["config"])

        # Validate series section
        self._validate_series_section(config["series"])

    def _validate_config_section(self, config_section: Dict[str, Any]) -> None:
        """Validate the config section."""
        for key in self.REQUIRED_CONFIG_KEYS:
            if key not in config_section:
                raise ConfigValidationError(f"Missing required config key: {key}")

        # Validate output directory
        output_dir = config_section.get("output_dir")
        if not output_dir:
            raise ConfigValidationError("output_dir cannot be empty")

        # Try to create the directory if it doesn't exist
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigValidationError(
                f"Cannot create output directory '{output_dir}': {e}"
            )

    def _validate_series_section(self, series_list: List[Dict[str, Any]]) -> None:
        """Validate the series section."""
        if not isinstance(series_list, list):
            raise ConfigValidationError("Series must be a list")

        if not series_list:
            raise ConfigValidationError("At least one series must be configured")

        for i, series in enumerate(series_list):
            try:
                self._validate_series_entry(series, i)
            except ConfigValidationError as e:
                raise ConfigValidationError(f"Series {i}: {e}")

    def _validate_series_entry(self, series: Dict[str, Any], index: int) -> None:
        """Validate a single series entry."""
        if not isinstance(series, dict):
            raise ConfigValidationError("Series entry must be a dictionary")

        # Check required keys
        for key in self.REQUIRED_SERIES_KEYS:
            if key not in series:
                raise ConfigValidationError(f"Missing required key: {key}")

        # Validate name
        name = series.get("name", "")
        if not name or not name.strip():
            raise ConfigValidationError("Series name cannot be empty")

        # Validate URL
        url = series.get("url", "")
        if not self._is_valid_url(url):
            raise ConfigValidationError(f"Invalid URL: {url}")

        # Validate narrator
        narrator = series.get("narrator", "")
        if narrator not in self.VALID_NARRATORS:
            raise ConfigValidationError(
                f"Invalid narrator '{narrator}'. Must be one of: {', '.join(self.VALID_NARRATORS)}"
            )

        # Check if narrator audio file exists
        narrator_file = self.speakers_dir / f"{narrator}.wav"
        if not narrator_file.exists():
            raise ConfigValidationError(
                f"Narrator audio file not found: {narrator_file}"
            )

        # Validate latest URL if present
        latest = series.get("latest", "")
        if latest and not self._is_valid_url(latest):
            raise ConfigValidationError(f"Invalid latest URL: {latest}")

        # Validate system configuration if present
        system = series.get("system", {})
        if system:
            self._validate_system_config(system)

        # Validate replacements if present
        replacements = series.get("replacements", {})
        if replacements and not isinstance(replacements, dict):
            raise ConfigValidationError("Replacements must be a dictionary")

    def _validate_system_config(self, system: Dict[str, Any]) -> None:
        """Validate system configuration."""
        system_types = system.get("type", [])
        if system_types:
            if not isinstance(system_types, list):
                raise ConfigValidationError("System types must be a list")

            for system_type in system_types:
                if system_type not in self.VALID_SYSTEM_TYPES:
                    raise ConfigValidationError(
                        f"Invalid system type '{system_type}'. "
                        f"Must be one of: {', '.join(self.VALID_SYSTEM_TYPES)}"
                    )

        # Validate speed if present
        speed = system.get("speed")
        if speed is not None:
            if not isinstance(speed, (int, float)) or speed <= 0:
                raise ConfigValidationError("System speed must be a positive number")

        # Validate modulate if present
        modulate = system.get("modulate")
        if modulate is not None and not isinstance(modulate, bool):
            raise ConfigValidationError("System modulate must be a boolean")

        # Validate voice if present
        voice = system.get("voice")
        if voice and voice not in self.VALID_NARRATORS:
            raise ConfigValidationError(
                f"Invalid system voice '{voice}'. Must be one of: {', '.join(self.VALID_NARRATORS)}"
            )

    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid."""
        if not url:
            return False

        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
