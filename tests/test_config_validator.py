import pytest
from pathlib import Path
from audiobook.validators.config_validator import ConfigValidator, ConfigValidationError

class TestConfigValidator:
    """Test cases for ConfigValidator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ConfigValidator()
        
        # Create a temporary speakers directory for testing
        self.speakers_dir = Path("test_speakers")
        self.speakers_dir.mkdir(exist_ok=True)
        
        # Create test speaker files
        for narrator in ['onyx', 'katie', 'john']:
            (self.speakers_dir / f"{narrator}.wav").touch()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if self.speakers_dir.exists():
            shutil.rmtree(self.speakers_dir)
    
    def test_valid_config(self):
        """Test that a valid configuration passes validation."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'latest': 'https://www.royalroad.com/fiction/test/chapter/1'
                }
            ]
        }
        
        # Should not raise any exception
        self.validator.validate_config(config)
    
    def test_missing_config_section(self):
        """Test that missing config section raises error."""
        config = {
            'series': []
        }
        
        with pytest.raises(ConfigValidationError, match="Missing 'config' section"):
            self.validator.validate_config(config)
    
    def test_missing_series_section(self):
        """Test that missing series section raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            }
        }
        
        with pytest.raises(ConfigValidationError, match="Missing 'series' section"):
            self.validator.validate_config(config)
    
    def test_missing_output_dir(self):
        """Test that missing output_dir raises error."""
        config = {
            'config': {},
            'series': []
        }
        
        with pytest.raises(ConfigValidationError, match="Missing required config key: output_dir"):
            self.validator.validate_config(config)
    
    def test_empty_series_list(self):
        """Test that empty series list raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': []
        }
        
        with pytest.raises(ConfigValidationError, match="At least one series must be configured"):
            self.validator.validate_config(config)
    
    def test_missing_required_series_keys(self):
        """Test that missing required series keys raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series'
                    # Missing url and narrator
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Missing required key: url"):
            self.validator.validate_config(config)
    
    def test_invalid_url(self):
        """Test that invalid URL raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'not-a-valid-url',
                    'narrator': 'onyx'
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Invalid URL: not-a-valid-url"):
            self.validator.validate_config(config)
    
    def test_invalid_narrator(self):
        """Test that invalid narrator raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'invalid_narrator'
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Invalid narrator 'invalid_narrator'"):
            self.validator.validate_config(config)
    
    def test_missing_narrator_file(self):
        """Test that missing narrator audio file raises error."""
        # Create a validator that uses the test speakers directory
        test_validator = ConfigValidator(speakers_dir=self.speakers_dir)
        
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx'  # Use a valid narrator name
                }
            ]
        }
        
        # Remove the test speaker file to simulate missing file
        narrator_file = self.speakers_dir / "onyx.wav"
        narrator_file.unlink()
        
        with pytest.raises(ConfigValidationError, match="Narrator audio file not found"):
            test_validator.validate_config(config)
    
    def test_invalid_system_type(self):
        """Test that invalid system type raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'system': {
                        'type': ['invalid_type']
                    }
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Invalid system type 'invalid_type'"):
            self.validator.validate_config(config)
    
    def test_invalid_system_speed(self):
        """Test that invalid system speed raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'system': {
                        'speed': -1
                    }
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="System speed must be a positive number"):
            self.validator.validate_config(config)
    
    def test_invalid_system_modulate(self):
        """Test that invalid system modulate raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'system': {
                        'modulate': 'not_a_boolean'
                    }
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="System modulate must be a boolean"):
            self.validator.validate_config(config)
    
    def test_invalid_replacements(self):
        """Test that invalid replacements raises error."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'replacements': 'not_a_dict'
                }
            ]
        }
        
        with pytest.raises(ConfigValidationError, match="Replacements must be a dictionary"):
            self.validator.validate_config(config)
    
    def test_valid_system_config(self):
        """Test that valid system configuration passes validation."""
        config = {
            'config': {
                'output_dir': '/tmp/test_output'
            },
            'series': [
                {
                    'name': 'Test Series',
                    'url': 'https://www.royalroad.com/fiction/test',
                    'narrator': 'onyx',
                    'system': {
                        'type': ['bold', 'italic'],
                        'speed': 1.2,
                        'modulate': True,
                        'voice': 'katie'
                    }
                }
            ]
        }
        
        # Should not raise any exception
        self.validator.validate_config(config)
