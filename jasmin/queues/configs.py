"""
Config file handler for 'amqp-broker' section in jasmin.cfg
"""

import logging
import os
import re

import txamqp

from jasmin.config import ConfigFile, ROOT_PATH, LOG_PATH

CONFIG_PATH = os.getenv('CONFIG_PATH', '%s/etc/jasmin/' % ROOT_PATH)
RESOURCE_PATH = os.getenv('RESOURCE_PATH', '%s/resource/' % CONFIG_PATH)
CLOUDAMQP_URL = os.getenv('CLOUDAMQP_URL', None)

class AmqpConfig(ConfigFile):
    """Config handler for 'amqp-broker' section"""

    def __init__(self, config_file=None):
        ConfigFile.__init__(self, config_file)

        if CLOUDAMQP_URL is not None:
            # Take rabbitmq config from CLOUDAMQP_URL env variable (used by heroku)
            self.username, self.password, self.host, self.vhost = \
                re.search(r"^amqps\:\/\/([a-z]+)\:([A-Za-z0-9_-]+)@((?!-)[-a-zA-Z0-9.]{1,63}(?<!-))\/([a-z]+)$",
                          CLOUDAMQP_URL).groups()
        else:
            self.host = self._get('amqp-broker', 'host', '127.0.0.1')
            self.username = self._get('amqp-broker', 'username', 'guest')
            self.password = self._get('amqp-broker', 'password', 'guest')
            self.vhost = self._get('amqp-broker', 'vhost', '/')

        self.port = self._getint('amqp-broker', 'port', 5672)
        self.spec = self._get('amqp-broker', 'spec', '%s/amqp0-9-1.xml' % RESOURCE_PATH)
        self.heartbeat = self._getint('amqp-broker', 'heartbeat', 0)

        # Logging
        self.log_level = logging.getLevelName(self._get('amqp-broker', 'log_level', 'INFO'))
        self.log_file = self._get('amqp-broker', 'log_file', '%s/amqp-client.log' % LOG_PATH)
        self.log_rotate = self._get('amqp-broker', 'log_rotate', 'W6')
        self.log_format = self._get(
            'amqp-broker', 'log_format', '%(asctime)s %(levelname)-8s %(process)d %(message)s')
        self.log_date_format = self._get('amqp-broker', 'log_date_format', '%Y-%m-%d %H:%M:%S')

        # Reconnection
        self.reconnectOnConnectionLoss = self._getbool('amqp-broker', 'connection_loss_retry', True)
        self.reconnectOnConnectionFailure = self._getbool('amqp-broker', 'connection_failure_retry', True)
        self.reconnectOnConnectionLossDelay = self._getint('amqp-broker', 'connection_loss_retry_delay', 10)
        self.reconnectOnConnectionFailureDelay = self._getint(
            'amqp-broker', 'connection_failure_retry_delay', 10)

    def getSpec(self):
        """Will return the specifications from self.spec file"""

        return txamqp.spec.load(self.spec)
