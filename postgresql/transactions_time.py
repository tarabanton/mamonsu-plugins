# -*- coding: utf-8 -*-

from mamonsu.plugins.pgsql.plugin import PgsqlPlugin as Plugin
from mamonsu.plugins.pgsql.pool import Pooler


class TransactionTime(Plugin):
    Interval = 60

    DEFAULT_CONFIG = {
        'system_users': '["pguser", "postgres", "pgpool", "bucardo", "londiste", "skytools"]'
    }

    Items = [
        # key, zbx_key, description,
        #    ('graph name', color, side), units, delta

        ('active', 'transactions.time[active]', 'max transaction duration: active',
            ('PostgreSQL instance: duration', '0000CC', 1),
            Plugin.UNITS.s, Plugin.DELTA.as_is),
        # ('idle', 'transactions.time[idle]', 'max transaction duration: idle',
        #     ('PostgreSQL instance: rate', 'CC0000', 0),
        #     Plugin.UNITS.s, Plugin.DELTA.as_is),
        ('idle in transaction', 'transactions.time[idle_in_transaction]', 'max transaction duration: idle_in_transaction',
            ('PostgreSQL transaction: duration', '00CC00', 0),
            Plugin.UNITS.s, Plugin.DELTA.as_is)
    ]

    def run(self, zbx):
        users = self.plugin_config('system_users', as_json=True)
        result = Pooler.query('SELECT \
                              state, \
                              coalesce(extract(epoch from age(now(), min(query_start))), 0) as max_time \
                              FROM pg_stat_activity WHERE lower(usename) \
                              NOT SIMILAR TO \'({})\' \
                              GROUP BY state'.format('|'.join(users)))
        for item in self.Items:
            state, key, val = item[0], item[1], 0
            for row in result:
                if row[0] != state:
                    continue
                else:
                    val = row[1]
                    break
            zbx.send('pgsql.{0}'.format(key), float(val))
        del result

    def items(self, template):
        result = ''
        for item in self.Items:
            result += template.item({
                'key': 'pgsql.{0}'.format(item[1]),
                'name': 'PostgreSQL {0}'.format(item[2]),
                'value_type': self.VALUE_TYPE.numeric_float,
                'units': item[4]
            })
        return result

    def graphs(self, template):
        graphs_name = ['PostgreSQL transaction: duration']
        result = ''
        for name in graphs_name:
            items = []
            for item in self.Items:
                if item[3][0] == name:
                    items.append({
                        'key': 'pgsql.{0}'.format(item[1]),
                        'color': item[3][1],
                        'yaxisside': item[3][2]
                    })
            graph = {'name': name, 'items': items}
            result += template.graph(graph)

        return result
