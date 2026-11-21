from datetime import datetime,timedelta,timezone
from src.config.database import Base,engine,Session
from src.models.entities import Arrival,LoadBatch,CargoLot,OutboundOption
from src.utils.time import now_utc,SH

# 接驳配载演练数据：跨午夜进站、贪心漏配结构、未到发/未发班次。
# 自然编号幂等，重复运行不覆盖人工修订；业务日为运行当日的昨日（上海）。

def at(day,h,m):return datetime(day.year,day.month,day.day,h,m,tzinfo=SH).astimezone(timezone.utc).isoformat()

def seed():
 Base.metadata.create_all(engine);now=now_utc();day=now.astimezone(SH).date()-timedelta(days=1);nxt=day+timedelta(days=1)
 rows=[
  ('LG-901','北站',at(day,23,50),at(nxt,0,12),'跨午夜进站：计划前日23:50，实际次日00:12'),
  ('LG-904','北站',at(day,23,55),at(nxt,0,24),'跨午夜进站：计划前日23:55，实际次日00:24'),
  ('LG-905','北站',at(day,23,58),None,'进站未到发，暂不配载'),
  ('LG-902','北站',at(nxt,0,30),at(nxt,0,30),'出港候选O1：舱位小、换装宽松'),
  ('LG-903','北站',at(nxt,1,0),at(nxt,1,0),'出港候选O2：换装要求高'),
  ('LG-906','北站',at(nxt,2,0),None,'出港未发，暂不作候选'),
 ]
 with Session() as s:
  for code,station,planned,actual,note in rows:
   if not s.query(Arrival).filter_by(code=code).first():s.add(Arrival(code=code,station=station,planned_at=planned,actual_at=actual,note=note))
  if not s.query(LoadBatch).filter_by(station='北站',business_day=day.isoformat()).first():
   b=LoadBatch(station='北站',business_day=day.isoformat(),state='pending',stale_note='首次计算',created_by='seed',created_at=now.isoformat())
   s.add(b);s.flush()
   for code,volume in [('LG-901',10),('LG-904',10),('LG-905',6)]:s.add(CargoLot(batch_id=b.id,code=code,volume=volume,note='演练货量'))
   for code,cap,mt in [('LG-902',10,5),('LG-903',10,40),('LG-906',8,10)]:s.add(OutboundOption(batch_id=b.id,code=code,capacity=cap,min_transfer=mt))
  s.commit()
  print({'arrivals':s.query(Arrival).count(),'load_batches':s.query(LoadBatch).count(),'business_day':day.isoformat()})
if __name__=='__main__':seed()
