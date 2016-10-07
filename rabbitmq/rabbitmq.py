# -*- coding: utf-8 -*-

"""
[rabbitmq]
enabled = False
;nodename = socket.gethostname()
host = 127.0.0.1
port = 15672
protocol = http
username = testuser
password = testuserpassword
filters =
;For example, the following filter could find all the durable queues: filter = {"durable": true}
;To only use the durable queues for a given vhost, the filter would be: filter = {"durable": true, "vhost": "mine"}
;To supply a list of queue names, the filter would be: filter = [{"name": "mytestqueuename"}, {"name": "queue2"}]
"""

import socket
import parser
import requests
try:
    import json
except:
    import simplejson as json
from mamonsu.lib.plugin import Plugin


class RabbitMQ(Plugin):
    Interval = 20

    DEFAULT_CONFIG = {
        'enabled': str(False),
        'nodename': str(socket.gethostname()),
        'host': '127.0.0.1',
        'port': '15672',
        'protocol': 'http',
        'username': str(None),
        'password': str(None),
        'filters': str(None),
    }

    overview_metrics = [ 'rabbitmq_version' ]
    node_discovery = False
    node_metrics = ['partitions',
                    'disk_free',
                    'fd_used', 'fd_total',
                    'mem_used', 'mem_limit',
                    'sockets_used', 'sockets_total',
                    #'proc_used', 'proc_total'
                    ]
    queue_discovery = True
    queue_metrics = ['memory', 'messages', 'messages_unacknowledged', 'consumers']

    def run(self, zbx):
        self.log.debug('Start run')
        check = self._check_aliveness()
        data_node = self._node_status(self.plugin_config('nodename'))
        data_queue = self._queues_status(self.plugin_config('nodename'))
        data = self.merge_dicts(check, data_node, data_queue)
        for item in data:
            zbx.send(item, zbx.json(data[item]))

    def _call_api(self, path):
        """
        Call the REST API and convert the results into JSON.
        :param path: str
        """
        url = '{0}://{1}:{2}/api/{3}'.format(self.plugin_config('protocol'), self.plugin_config('host'), self.plugin_config('port'), path)
        self.log.debug('Issuing RabbitMQ API call to get data on ' + str(url))
        try:
            r = requests.get(url, auth=(self.plugin_config('username'), self.plugin_config('password')))
            data = r.text
            return json.loads(data)
        except requests.exceptions.RequestException as e:
            self.log.error('RabbitMQ API call error: {0}'.format(e))

    def _node_status(self, nodename):
        """
        Get node status metrics
        :param nodename: str
        :return: array
        """
        data = {}
        nodes = []
        nodename = nodename.split('.')[0]
        self.log.debug('Getting node status data for node "{0}"'.format(nodename))
        for nodeData in self._call_api('nodes'):
            nodes.append({'{#NODENAME}': nodeData['name'].split('@')[1], '{#NODETYPE}': nodeData['type']})
            if nodename in nodeData['name']:
                for item in self.node_metrics:
                    data['rabbitmq[server,'+item+']'] = nodeData.get(item)
        if self.node_discovery:
            data['rabbitmq.discovery_nodes[]'] = {'data': nodes}

        overview = self._call_api('overview')
        if nodename in overview['node']:
            data['rabbitmq[server,message_stats_publish]'] = overview.get('message_stats', {}).get('publish', 0)
            data['rabbitmq[server,message_stats_deliver_get]'] = overview.get('message_stats', {}).get('deliver_get', 0)
            data['rabbitmq[server,rabbitmq_version]'] = overview.get('rabbitmq_version', 'None')

        self.log.debug('Got node status data: {0}'.format(data))
        return data

    def _queues_status(self, nodename):
        """
        Get queues metrics
        :param nodename: str
        :return: array
        """
        data = {}
        queues = []
        nodename = nodename.split('.')[0]
        self.log.debug('Getting queues data for node "{0}"'.format(nodename))
        for queueData in self._filter_queues(self._call_api('queues'), filters=self.plugin_config('filters')):
            if nodename in queueData['node']:
                queues.append({'{#VHOSTNAME}': queueData['vhost'], '{#QUEUENAME}': queueData['name']})
                for item in self.queue_metrics:
                    data['rabbitmq.queues[{0},queue_{1},{2}]'.format(queueData['vhost'], item, queueData['name'])] = queueData.get(item)
                for item in ['deliver_get', 'publish']:
                    data['rabbitmq.queues[{0},queue_message_stats_{1},{2}]'.format(queueData['vhost'], item, queueData['name'])] = queueData.get('message_stats', {}).get(item, 0)
        if self.queue_discovery:
            data['rabbitmq.discovery_queue[]'] = {'data': queues}

        self.log.debug('Got queues data: {0}'.format(data))
        return data

    def _filter_queues(self, queues_data, filters=None):
        """Return only items matching filters"""
        if filters:
            try:
                filters = json.loads(filters)
            except KeyError:
                parser.error('Invalid filters object.')
        else:
            filters = [{}]
        if not isinstance(filters, (list, tuple)):
            filters = [filters]

        data = []
        self.log.debug("Filtering out by {}".format(str(filters)))
        if not filters:
            filters = [{}]
        for queue in queues_data:
            success = False
            for _filter in filters:
                check = [(x, y) for x, y in queue.items() if x in _filter]
                shared_items = set(_filter.items()).intersection(check)
                if len(shared_items) == len(_filter):
                    success = True
                    break
            if success:
                data.append(queue)
        self.log.debug('Got FILTERED queues data: {0}'.format(len(data)))
        return data

    def _check_aliveness(self):
        """Check the aliveness status of a given vhost."""
        data = {}
        data['rabbitmq[check_aliveness]'] = self._call_api('aliveness-test/%2f')['status']
        self.log.debug('Aliveness test: {0}'.format(data['rabbitmq[check_aliveness]']))
        return data

    @staticmethod
    def merge_dicts(self, *dict_args):
        """
        Given any number of dicts, shallow copy and merge into a new dict,
        precedence goes to key value pairs in latter dicts.
        :param dict_args: dicts list
        """
        result = {}
        for d in dict_args:
            result.update(d)
        return result
