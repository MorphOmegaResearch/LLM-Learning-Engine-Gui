import configparser
import os

class ConfigManager:
    """Manages reading and writing of the application's config.ini file."""
    def __init__(self, filename='config.ini'):
        self.filename = os.path.join(os.path.dirname(__file__), filename)
        self.config = configparser.ConfigParser()
        if not os.path.exists(self.filename):
            self.create_default_config()
        self.config.read(self.filename)

    def create_default_config(self):
        """Creates a default config.ini file if one does not exist."""
        self.config['Window'] = {
            'width': '850',
            'height': '650'
        }
        self.config['Endpoints'] = {
            'ollama_url': 'http://localhost:11434/api/generate',
            'gemini_api_key': 'AIzaSyD--89l4KBOSpjqmzRib5ctuD6-5GDHDvI'
        }
        self.config['Ollama'] = {
            'model': 'llama2',
            'num_gpu': ''
        }
        self.config['Gemini'] = {
            'model': 'gemini-1.5-flash',
            'available_models': 'gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp, gemini-3-flash, gemini-3-pro'
        }
        self.config['ResourceProfiles'] = {
            'max_gpu_layers': '999',
            'balanced_layers': '25',
            'cpu_only_layers': '0'
        }
        self.config['Application'] = {
            'auto_refresh_seconds': '5'
        }
        self.save()
        # Re-read the config after saving to ensure consistency
        self.config.read(self.filename)

    def get(self, section, option, fallback=None):
        """Gets a value from the config file."""
        return self.config.get(section, option, fallback=fallback)

    def getint(self, section, option, fallback=None):
        """Gets an integer value from the config file."""
        try:
            return self.config.getint(section, option, fallback=fallback)
        except (ValueError, TypeError):
            return fallback if fallback is not None else 0


    def set(self, section, option, value):
        """Sets a value in the config."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))

    def save(self):
        """Saves the current configuration to the file."""
        with open(self.filename, 'w') as configfile:
            self.config.write(configfile)
