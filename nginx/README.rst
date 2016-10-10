Nginx log parsing plugin
------------------------
When running on Debian-based OSes, by-default mamonsu have no access to nginx log files.
Either change settings on nginx, or add mamonsu user to adm group.

Default configuration
    [nginx]
    enabled = False
    ;URL to nginx stat (http_stub_status_module)
    url = http://127.0.0.1/nginx_status
    ;Nginx log file path
    file = /var/log/nginx/access.log
    ;Optional Basic Auth
    username =
    password =
    http_codes = {200, 301, 302, 304, 403, 404, 499, 500, 502, 503, 520}

