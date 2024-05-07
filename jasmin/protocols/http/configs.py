"""
Config file handler for 'http-api' section in jasmin.cfg
"""

import logging
import os
from jasmin.config import ConfigFile, LOG_PATH


class HTTPApiConfig(ConfigFile):
    """Config handler for 'http-api' section"""

    def __init__(self, config_file=None):
        ConfigFile.__init__(self, config_file)

        self.bind = self._get('http-api', 'bind', os.getenv('API_BIND', '0.0.0.0'))
        self.port = self._getint('http-api', 'port', int(os.getenv('API_PORT', 1401)))

        self.billing_feature = self._getbool('http-api', 'billing_feature', True)

        # Logging
        self.access_log = self._get(
            'http-api', 'access_log', '%s/http-accesslog.log' % LOG_PATH)
        self.log_level = logging.getLevelName(self._get('http-api', 'log_level', 'INFO'))
        self.log_file = self._get('http-api', 'log_file', '%s/http-api.log' % LOG_PATH)
        self.log_rotate = self._get('http-api', 'log_rotate', 'W6')
        self.log_format = self._get(
            'http-api', 'log_format', '%(asctime)s %(levelname)-8s %(process)d %(message)s')
        self.log_date_format = self._get('http-api', 'log_date_format', '%Y-%m-%d %H:%M:%S')
        self.log_privacy = self._getbool('http-api', 'log_privacy', False)

        # Long message splitting
        self.long_content_max_parts = self._get('http-api', 'long_content_max_parts', 5)
        self.long_content_split = self._get('http-api', 'long_content_split', 'udh')  # sar or udh
