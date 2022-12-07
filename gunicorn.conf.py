# gunicorn inaflask:app
bind = '0.0.0.0:9527'
workers = 2
timeout = 10
