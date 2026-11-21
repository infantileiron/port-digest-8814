import os,time,logging
from pathlib import Path
import redis
from redis.exceptions import LockError
from src.config.database import Session
from src.services.scheduler import run_due
from src.services.loadplan import compute_pending
from src.utils.time import now_utc
r=redis.Redis.from_url(os.environ['REDIS_URL'])
while True:
 Path('/tmp/heartbeat').touch()
 try:
  with r.lock('port-digest:scheduler',timeout=20,blocking_timeout=0):
   with Session() as s:run_due(s,now_utc())
   with Session() as s:compute_pending(s,now_utc())
 except LockError:pass
 except Exception:logging.exception('scheduler tick failed')
 time.sleep(1)
