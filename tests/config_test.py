import unittest
import logging
from zoneinfo import ZoneInfo
from BAScraper.BAConfig import BAConfig
from tzlocal import get_localzone

class TestBaseConfig(unittest.TestCase):
    def test_default_timezone_auto(self):
        """Test that default 'auto' timezone resolves to local timezone key."""
        config = BAConfig()
        local_tz_key = get_localzone().key
        self.assertEqual(config.timezone, local_tz_key)
        self.assertIsInstance(config.get_timezone_object(), ZoneInfo)
        self.assertEqual(config.get_timezone_object().key, local_tz_key)

    def test_explicit_valid_timezone(self):
        """Test setting a valid explicit timezone."""
        config = BAConfig(timezone="UTC")
        self.assertEqual(config.timezone, "UTC")
        self.assertEqual(config.get_timezone_object().key, "UTC")

        config_ny = BAConfig(timezone="America/New_York")
        self.assertEqual(config_ny.timezone, "America/New_York")

    def test_invalid_timezone(self):
        """Test that invalid timezones raise ValueError."""
        with self.assertRaises(ValueError) as cm:
            BAConfig(timezone="Invalid/Timezone")
        self.assertIn("Invalid timezone", str(cm.exception))

    def test_logging_config_defaults(self):
        """Test default logging configuration."""
        config = BAConfig()
        self.assertEqual(config.logging_config["level"], logging.INFO)
        self.assertTrue("format" in config.logging_config)

    def test_logging_config_custom(self):
        """Test overriding logging configuration."""
        custom_logging = {
            "level": logging.DEBUG,
            "format": "%(message)s"
        }
        config = BAConfig(logging_config=custom_logging)
        self.assertEqual(config.logging_config["level"], logging.DEBUG)
        self.assertEqual(config.logging_config["format"], "%(message)s")

if __name__ == '__main__':
    unittest.main()
