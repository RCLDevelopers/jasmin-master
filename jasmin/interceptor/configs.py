"""
Config file handlers for 'interceptor' section in interceptor.cfg
"""

import binascii
import logging
import os

from jasmin.config import ConfigFile, ROOT_PATH, LOG_PATH

CONFIG_PATH = os.getenv('CONFIG_PATH', '%s/etc/jasmin/' % ROOT_PATH)
RESOURCE_PATH = os.getenv('RESOURCE_PATH', '%s/resource/' % CONFIG_PATH)


class InterceptorPBConfig(ConfigFile):
    """Config handler for 'interceptor' section"""

    def __init__(self, config_file=None):
        ConfigFile.__init__(self, config_file)

        self.bind = self._get('interceptor', 'bind', '0.0.0.0')
        self.port = self._getint('interceptor', 'port', 8987)

        self.authentication = self._getbool('interceptor', 'authentication', True)
        self.admin_username = self._get('interceptor', 'admin_username', 'iadmin')
        self.admin_password = binascii.unhexlify(self._get('interceptor', 'admin_password',
                                                           "dd8b84cdb60655fed3b9b2d668c5bd9e"))

        # Logging
        self.log_level = logging.getLevelName(self._get('interceptor', 'log_level', 'INFO'))
        self.log_rotate = self._get('interceptor', 'log_rotate', 'W6')
        self.log_file = self._get('interceptor', 'log_file', '%s/interceptor.log' % LOG_PATH)
        self.log_format = self._get(
            'interceptor', 'log_format', '%(asctime)s %(levelname)-8s %(process)d %(message)s')
        self.log_date_format = self._get('interceptor', 'log_date_format', '%Y-%m-%d %H:%M:%S')

        self.log_slow_script = self._getint('interceptor', 'log_slow_script', 1)


class InterceptorPBClientConfig(ConfigFile):
    """Config handler for 'interceptor-client' section"""

    def __init__(self, config_file=None):
        ConfigFile.__init__(self, config_file)

        self.host = self._get('interceptor-client', 'host', '127.0.0.1')
        self.port = self._getint('interceptor-client', 'port', 8987)

        self.username = self._get('interceptor-client', 'username', 'iadmin')
        self.password = self._get('interceptor-client', 'password', 'ipwd')
