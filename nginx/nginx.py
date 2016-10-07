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
        'password': str(None),
        'http_codes': '{200, 301, 302, 304, 403, 404, 499, 500, 502, 503, 520}'
    }

    Items = [
        # zbx_key, name, color
        ('active_connections', 'Active connections ', 'C80000'),
        ('keepalive_connections', 'Keep-alive connections', '00C800'),
        ('accepted_connections', 'Accepted connections', 'C80000'),
        ('handled_connections', 'Handled connections', '00C800'),
        ('handled_requests', 'Handled requests', 'CC00CC'),
        ('header_reading', 'Establishing connection', None),
        ('body_reading', 'Slab: Kernel used memory (inode cache)', None),
        ('rps', 'Requests\sec', '00C800'),
        ('200', '200 - OK', 'C80000'),
        ('301', '301 - Moved Permanently', '00C800'),
        ('302', '302 - Moved Temporarily', '0000C8'),
        ('304', '304 - Not Modified', 'C800C8'),
        ('403', '403 - Forbidden', '00C8C8'),
        ('404', '404 - Not Found', 'C8C800'),
        ('499', '499 - Connection Reset', 'C8C8C8'),
        ('500', '500 - Internal Error', '960000'),
        ('502', '502 - Bad Gateway', '66FF66'),
        ('503', '503 - Service unavailable', '009600'),
        ('520', '520 - Custom code', 'BB2A02')
    ]

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
            with open(self.plugin_config('file'), 'r') as logfile:
                # Codes to always initialize
                nginx_http_codes = self.plugin_config('http_codes')
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
                    except:
                        new_seek = seek = os.path.getsize(self.plugin_config('file'))
                    finally:
                        f.close()
                else:
                    new_seek = seek = os.path.getsize(self.plugin_config('file'))

                # if log file became larger - continue from last point, else start from 0
                if os.path.getsize(self.plugin_config('file')) > seek:
                    self.log.debug('Continuing old log file at ' + str(seek) + ' bytes')
                    logfile.seek(seek)

                self.log.debug('Parsing log file')
                for line in logfile:
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
            # zbx.send('nginx[rps]', int(round(rps / 60)))
            # Adding the request per seconds to response
            for second in range(0, 60):
                zbx.send('nginx[rps]', rps[second], host=None, clock=(minute + second))
            # Adding the response codes stats to response
            for t in res_code:
                zbx.send('nginx[{0}]'.format(t), res_code[t])
        except Exception as e:
            self.log.error('Getting access log info error: {0}'.format(e))

    def items(self, template):
        result = ''
        for item in self.Items:
            result += template.item({
                'name': '{0}'.format(item[1]),
                'key': 'nginx[{0}]'.format(item[0]),
            })
        return result

    #TODO: Graphs graphs graphs
    def graphs(self, template):
        items = []
        # Nginx connections
        for metric in ['active_connections', 'keepalive_connections']:
            for t in self.Items:
                if t[0] == metric:
                    items.append({
                        'key': 'nginx[{0}]'.format(t[0]),
                        'color': t[2]
                    })
        # graph = {
        #     'name': 'Memory overview', 'height': 400,
        #     'type': 1, 'items': items}
        return template.graph(graph)
