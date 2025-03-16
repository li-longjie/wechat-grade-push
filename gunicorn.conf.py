# 绑定的ip与端口
bind = "0.0.0.0:5000"

# 工作进程数
workers = 1  # 设置为1避免多进程问题

# 工作模式
worker_class = "sync"

# 日志配置
accesslog = "/var/log/grade-push-access.log"
errorlog = "/var/log/grade-push.log"
loglevel = "info"

# 进程名称
proc_name = "grade_push"

# 超时设置
timeout = 120
keepalive = 65

# 重启设置
max_requests = 1000
max_requests_jitter = 50

# 优雅重启
graceful_timeout = 30

# 调试设置
capture_output = True
enable_stdio_inheritance = True

# 进程环境变量
def worker_int(worker):
    worker.cfg.env = worker.cfg.env or {}
    worker.cfg.env['GUNICORN_WORKER_TYPE'] = 'worker'

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid) 