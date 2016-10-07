# -*- coding: utf-8 -*-

"""
[skytools]
enabled = False
"""

import os
from mamonsu.plugins.pgsql.plugin import PgsqlPlugin as Plugin
from mamonsu.plugins.pgsql.pool import Pooler

class Skytools(Plugin):

    DEFAULT_CONFIG = {
        'enabled': str(False)
    }

    def run(self, zbx):
        data = {}
        consumers = []
        node_processes = []

        self.log.debug('Fetching queues list')
        for queue in Pooler.query('SELECT queue_name FROM pgq.get_queue_info()'):
            node_type = Pooler.query('SELECT node_type FROM pgq_node.get_node_info(\'{0}\')'.format(queue[0]))[0]
            if 'root' in node_type:
                skytools_processes = ['pgqd', 'londiste']
                node_processes.append({'{#PROCESS}': 'pgqd'})
                node_processes.append({'{#PROCESS}': 'londiste'})
            else:
                skytools_processes = ['londiste']
                node_processes.append({'{#PROCESS}': 'londiste'})
            self.log.debug('Node is {0} for queue {1}'.format(node_type, queue[0]))
        data['skytools.proc.discovery[]'] = {'data': node_processes}

        self.log.debug('Requesting current list of processes')
        try:
            proclist = os.popen('ps ax -o command')
            for p in skytools_processes:
                data['skytools.proc[{0}]'.format(p)] = 0
                for proc in proclist:
                    if p in proc:
                        data['skytools.proc[{0}]'.format(p)] += 1
                self.log.debug('Number of {0} processes: {1}'.format(p, data['skytools.proc[{0}]'.format(p)]))
        except OSError as e:
            self.log.error('Error while running command "ps ax -o command": {0}'.format(e))

        '''
        # Getting consumers list
        [queue_name | consumer_name | lag | last_seen | last_tick | current_batch | next_tick | pending_events]
        [u'queue', u'.global_watermark', datetime.timedelta(0, 637, 369631), datetime.timedelta(0, 75, 78907), 506617, None, None, 363],
        [u'queue', u'.subscriber.watermark', datetime.timedelta(0, 637, 369631), datetime.timedelta(0, 281, 403805), 506617, None, None, 363],
        [u'queue', u'subscriber', datetime.timedelta(0, 18, 44107), datetime.timedelta(0, 17, 806266), 506718, None, None, 0]
        '''
        self.log.debug('Fetching consumers list')
        for consumer in Pooler.query('SELECT * FROM pgq.get_consumer_info()'):
            if not consumer[1].startswith('.'):
                self.log.debug('Got Data - Queue: {0} | Consumer: {1} | Lag: {2} | Last seen: {3}'.format(consumer[0], consumer[1], consumer[2], consumer[3]))
                consumers.append({'{#QUEUE}': consumer[0],'{#CONSUMER}': consumer[1]})
                data['skytools.consumer.lag[{0},{1}]'.format(consumer[0], consumer[1])] = consumer[2].total_seconds()
                data['skytools.consumer.last_seen[{0},{1}]'.format(consumer[0], consumer[1])] = consumer[3].total_seconds()
                data['skytools.consumer.pending_events[{0},{1}]'.format(consumer[0], consumer[1])] = consumer[7]
        data['skytools.consumer.discovery[]'] = {'data': consumers}

        self.log.debug('Final data set: {0}'.format(data))
        for item in data:
            zbx.send(item, zbx.json(data[item]))