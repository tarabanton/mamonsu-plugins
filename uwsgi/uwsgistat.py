# -*- coding: utf-8 -*-

"""
[uwsgistat]
enabled = False
socket =
; socket is path to uwsgi stats
; sockets delimited by whitespaces
"""

import os
import socket
try:
    import simplejson as json
except ImportError:
    import json

from mamonsu.lib.plugin import Plugin

class Uwsgistat(Plugin):
    Interval = 30

    DEFAULT_CONFIG = {
        'enabled': str(False),
        'socket': str(None)
    }

    def run(self, zbx):
        uwsgistat_sockets = self.plugin_config('socket').split()
        zbx_data = {}
        zbx_instances = []
        self.log.debug('Sockets : {0}'.format(uwsgistat_sockets))
        for socket_addr in uwsgistat_sockets:
            self.log.debug('Working on socket : {0}'.format(socket_addr))
            if ':' in socket_addr:
                sfamily, addr, host = self.inet_addr(socket_addr)
                socket_name = socket_addr
            elif socket_addr.startswith('@'):
                sfamily, addr, host = self.abstract_unix_addr(socket_addr)
                socket_name = os.path.splitext(os.path.basename(socket_addr))[0]
            else:
                sfamily, addr, host = self.unix_addr(socket_addr)
                socket_name = os.path.splitext(os.path.basename(socket_addr))[0]

            js = ''
            try:
                s = socket.socket(sfamily, socket.SOCK_STREAM)
                s.connect(addr)

                while True:
                    data = s.recv(4096)
                    if len(data) < 1:
                        break
                    js += data.decode('utf8')

                zbx_data['uwsgi[{0},active]'.format(socket_name)] = 1

                result = {}
                dd = json.loads(js)

                result['version'] = ''
                result['total_requests'] = 0
                result['total_exceptions'] = 0
                result['avg_rt'] = 0

                if 'version' in dd:
                    result['version'] = dd['version']

                if 'workers' in dd:
                    result['total_workers'] = len(dd['workers'])
                    result['running_workers'] = 0
                    for worker in dd['workers']:
                        if not 'idle' in worker['status']:
                            result['running_workers'] += 1
                        result['total_requests'] += worker['requests']
                        result['total_exceptions'] += worker['exceptions']
                        result['avg_rt'] += worker['avg_rt']
                    #result['avg_requests'] = result['total_requests']/result['total_workers']
                    #result['avg_exceptions'] = result['total_requests']/result['total_workers']
                    #Converting microseconds to seconds
                    result['avg_rt'] = result['avg_rt']/result['total_workers']/1000000
                    result['workers_used'] = (result['running_workers']/result['total_workers'])*100

                self.log.debug('Got data for {}: {}'.format(socket_name, result))
                for key in result:
                   zbx_data['uwsgi[{0},{1}]'.format(socket_name,key)] = result[key]
            except IOError as e:
                self.log.error("Unable to get uWSGI statistics: {0}".format(e))
                zbx_data['uwsgi[{0},active]'.format(socket_name)] = 0
            finally:
                zbx_instances.append({'{#INSTANCE}': socket_name})
                s.close()

        zbx_data['uwsgi.discovery[]'] = {'data': zbx_instances}
        self.log.debug('Got ALL data: {}'.format(zbx_data))
        for item in zbx_data:
            zbx.send(item, zbx.json(zbx_data[item]))

    def inet_addr(self, arg):
        sfamily = socket.AF_INET
        host, port = arg.rsplit(':', 1)
        addr = (host, int(port))
        self.log.debug('Socket {0} belongs to AF_INET socket family'.format(arg))
        return sfamily, addr, host

    def unix_addr(self, arg):
        sfamily = socket.AF_UNIX
        addr = arg
        self.log.debug('Socket {0} belongs to AF_UNIX socket family'.format(arg))
        return sfamily, addr, socket.gethostname()

    def abstract_unix_addr(self, arg):
        sfamily = socket.AF_UNIX
        addr = '\0' + arg[1:]
        self.log.debug('Socket {0} belongs to AF_UNIX socket family'.format(arg))
        return sfamily, addr, socket.gethostname()
