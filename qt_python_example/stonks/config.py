import os, json
from .utils import singleton

DEFAULT_CONFIG_FOLDER = "%LOCALAPPDATA%\\StonX"

@singleton
class Config(object):
    def __init__(self, config_name='config', config_folder=DEFAULT_CONFIG_FOLDER):
        self.__config = None
        self._configPath = os.path.join(os.path.expandvars(config_folder), '{}.json'.format(config_name))
        print(self._configPath)
        if not os.path.isdir(os.path.dirname(self._configPath)):
            os.makedirs(os.path.dirname(self._configPath))

    def load_config(self):
        if not os.path.isfile(self._configPath):
            self.__config = {}
            return
        with open(self._configPath, 'r') as f:
            print('loading config')
            try:
                self.__config = json.load(f)
            except json.decoder.JSONDecodeError:
                print('WARNING: Invalid Config File')
                self.__config = {}

    def save_config(self):
        with open(self._configPath, 'w') as f:
            json.dump(self.__config, f)

    def get_property(self, property_name, default=None):
        if not self.__config:
            self.load_config()
        return self.__config.get(property_name, default)

    def set_property(self, property_name, value, save=True):
        if not self.__config:
            self.__config = {}
        self.__config[property_name] = value
        if save:
            self.save_config()
