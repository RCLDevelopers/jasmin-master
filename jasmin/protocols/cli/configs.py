"""
Config file handler for 'jcli' section in jasmin.cfg
"""

import logging
import binascii
from jasmin.config import ConfigFile, LOG_PATH


class JCliConfig(ConfigFile):
    """Config handler for 'jcli' section"""

    def __init__(self, config_file=None):
        ConfigFile.__init__(self, config_file)

        self.bind = self._get('jcli', 'bind', '127.0.0.1')
        self.port = self._getint('jcli', 'port', 8990)

        self.authentication = self._getbool('jcli', 'authentication', True)
        self.admin_username = self._get('jcli', 'admin_username', 'jcliadmin')
        self.admin_password = binascii.unhexlify(self._get('jcli', 'admin_password',
                                                           '79e9b0aa3f3e7c53e916f7ac47439bcb'))

        self.log_level = logging.getLevelName(self._get('jcli', 'log_level', 'INFO'))
        self.log_file = self._get('jcli', 'log_file', '%s/jcli.log' % LOG_PATH)
        self.log_rotate = self._get('jcli', 'log_rotate', 'W6')
        self.log_format = self._get(
            'jcli', 'log_format', '%(asctime)s %(levelname)-8s %(process)d %(message)s')
        self.log_date_format = self._get('jcli', 'log_date_format', '%Y-%m-%d %H:%M:%S')
