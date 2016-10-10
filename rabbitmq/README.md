RabbitMQ Server status plugin
------------------------
Requires `requests` python library

Default configuration
``` ini
[rabbitmq]
enabled = False
nodename = System Hostname
host = 127.0.0.1
port = 15672
protocol = http
username = testuser
password = testuserpassword
filters =
```

Filters
-------
Filter is a list of key-value pairs. Plugin selects only queues matching one of filters in list.

For example, the following filter could find all the durable queues:
`filter = {"durable": true}`

To only use the durable queues for a given vhost, the filter would be:
`filter = {"durable": true, "vhost": "mine"}`

To supply a list of queue names, the filter would be:
`filter = [{"name": "mytestqueuename"}, {"name": "queue2"}]`