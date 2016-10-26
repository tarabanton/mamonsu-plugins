# -*- coding: utf-8 -*-

"""
[gdnsd]
enabled = False
url = http://127.0.0.1:3506/json
;Optional Basic Auth
username =
password =
"""

import logging
import requests
try:
    import json
except:
    import simplejson as json

from mamonsu.lib.plugin import Plugin


class Gdnsd(Plugin):
    DEFAULT_CONFIG = {
        'enabled': str(False),
        'url': 'http://127.0.0.1:3506/json',
        'username': str(None),
        'password': str(None)
    }

    Status_Sections = ['stats','udp','tcp']
    State_Types = ['na', 'up', 'down']

    def run(self, zbx):
        data = {}
        self.log.debug('Start run')
        url = '{0}'.format(self.plugin_config('url'))
        self.log.debug('Getting status. URL = ' + str(url))
        try:
            requests_log = logging.getLogger("requests")
            requests_log.addHandler(logging.NullHandler())
            requests_log.propagate = False
            gdnsd_status = requests.get(url, auth=(self.plugin_config('username'), self.plugin_config('password'))).text
            #self.log.debug('Got status info')
            #self.log.debug(gdnsd_status)
            status = json.loads(gdnsd_status)
        except requests.exceptions.RequestException as e:
            self.log.error('Getting status error: {0}'.format(e))
            return None

        data['gdnsd[uptime]'] = status.get('uptime')

        for section in self.Status_Sections:
            for item in status[section]:
                data['gdnsd.{}[{}]'.format(section, item)] = status[section].get(item)

        data['gdnsd.services[total]'] = 0
        for state in self.State_Types:
            if not data.get('gdnsd.services[{}]'.format(state)):
                data['gdnsd.services[{}]'.format(state)] = 0
                data['gdnsd.services[{}.list]'.format(state)] = ""

        for service in status['services']:
            data['gdnsd.services[total]'] += 1
            data['gdnsd.services[{}]'.format(str(service['state']).lower())] += 1
            data['gdnsd.services[{}.list]'.format(str(service['state']).lower())] += str(service['service']) + '; '

        self.log.debug('Got node status data: {0}'.format(data))

        for item in data:
            zbx.send(item, zbx.json(data[item]))