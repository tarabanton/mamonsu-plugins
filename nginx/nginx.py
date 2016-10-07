# -*- coding: utf-8 -*-

"""
[nginx]
enabled = False
;URL to nginx stat (http_stub_status_module)
url = http://127.0.0.1/nginx_status
;Nginx log file path
file = /var/log/nginx/access.log
;Optional Basic Auth
username =
password =
"""

import re
import datetime
import time
import os.path
import requests
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2
from mamonsu.lib.plugin import Plugin

class Nginx(Plugin):

    DEFAULT_CONFIG = {
        'enabled': str(False),
        'url': 'http://127.0.0.1/nginx_status',
        'file': '/var/log/nginx/access.log',
        'username': str(None),
        'password': str(None)
    }

    def run(self, zbx):
        self.log.debug('Start run')
        url = '{0}'.format(self.plugin_config('url'))
        self.log.debug('Getting stub status. URL = ' + str(url))
        try:
            if self.plugin_config('username') and self.plugin_config('password'):
                self.log.debug('We have auth on stub status')
                basic_status = requests.get(url, auth=(self.plugin_config('username'), self.plugin_config('password')))
            else:
                basic_status = requests.get(url).text
            '''
            STUB STATUS nginx module output
            Active connections: 1
            server accepts handled requests
            2101898 2101898 1748083
            Reading: 0 Writing: 1 Waiting: 0
            '''
            self.log.debug('Got basic info')
            self.log.debug(basic_status)
            status = basic_status.split('\n')
            # Active connections
            zbx.send('nginx[active_connections]',
                     (re.match(r'(.*):\s(\d*)', status[0], re.M | re.I).group(2)))
            # Accepts
            zbx.send('nginx[accepted_connections]',
                     (re.match(r'\s(\d*)\s(\d*)\s(\d*)', status[2], re.M | re.I).group(1)))
            # Handled
            zbx.send('nginx[handled_connections]',
                     (re.match(r'\s(\d*)\s(\d*)\s(\d*)', status[2], re.M | re.I).group(2)))
            # Requests
            zbx.send('nginx[handled_requests]',
                     (re.match(r'\s(\d*)\s(\d*)\s(\d*)', status[2], re.M | re.I).group(3)))
            # Reading
            zbx.send('nginx[header_reading]',
                     (re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', status[3], re.M | re.I).group(2)))
            # Writing
            zbx.send('nginx[body_reading]',
                     (re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', status[3], re.M | re.I).group(4)))
            # Waiting
            zbx.send('nginx[keepalive_connections]',
                     (re.match(r'(.*):\s(\d*)(.*):\s(\d*)(.*):\s(\d*)', status[3], re.M | re.I).group(6)))
        except requests.exceptions.RequestException as e:
            self.log.error('Get nginx status error: {0}'.format(e))

        self.log.debug('Getting access log info')
        try:
            with open(self.plugin_config('file'), 'r') as file:
                # Codes to always initialize
                nginx_http_codes = {200, 301, 302, 304, 403, 404, 499, 500, 502, 503, 520}
                # Declare datetime
                d = datetime.datetime.now() - datetime.timedelta(minutes=1)
                minute = int(time.mktime(d.timetuple()) / 60) * 60
                d = d.strftime('%d/%b/%Y:%H:%M')
                total_rps = 0
                rps = [0] * 60
                # Nullify variables
                res_code = {}
                # Temp file, with log file cursor position
                seek_file = '/tmp/mamonsu_nginx_stat'

                if os.path.isfile(seek_file):
                    f = open(seek_file, 'r')
                    try:
                        new_seek = seek = int(f.readline())
                        f.close()
                    except:
                        #new_seek = seek = 0
                        new_seek = seek = os.path.getsize(self.plugin_config('file'))
                else:
                    #new_seek = seek = 0
                    new_seek = seek = os.path.getsize(self.plugin_config('file'))

                #if log file became larger - continue from last point, else start from 0
                if os.path.getsize(self.plugin_config('file')) > seek:
                    self.log.debug('Continuing old log file at '+str(seek)+' bytes')
                    file.seek(seek)

                self.log.debug('Parsing log file')
                for line in file:
                    if d in line:
                        total_rps += 1
                        sec = int(re.match('(.*):(\d+):(\d+):(\d+)\s', line).group(4))
                        code = int(re.match(r'(.*)"\s(\d*)\s', line).group(2))
                        if res_code.get(code):
                            res_code[code] += 1
                        else:
                            res_code[code] = 1
                        rps[sec] += 1

            if total_rps != 0:
                f = open(seek_file, 'w')
                f.write(str(new_seek))
                f.close()
            else:
                self.log.debug('Zero records processed')

            for code in nginx_http_codes:
                if not res_code.get(code):
                    res_code[code] = 0
            self.log.debug('Sending data to zabbix')
            #zbx.send('nginx[rps]', int(round(rps / 60)))
            # Adding the request per seconds to response
            for second in range(0, 60):
                    zbx.send('nginx[rps]', rps[second], host=None, clock=(minute + second))
            # Adding the response codes stats to response
            for t in res_code:
                zbx.send('nginx[{0}]'.format(t), res_code[t])
        except Exception as e:
            self.log.error('Getting access log info error: {0}'.format(e))
