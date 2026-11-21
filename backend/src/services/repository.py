from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from src.models.entities import Arrival,Subscription,Receipt,LoadBatch,CargoLot,OutboundOption
from src.services.business import dump
from src.utils.time import now_utc,next_due

def arrival_rows(s):return [dump(r) for r in s.query(Arrival).order_by(Arrival.planned_at,Arrival.id).all()]
def save_arrival(s,data,i=None):
 r=s.get(Arrival,i) if i else Arrival()
 if not r:raise HTTPException(404,'到发记录不存在')
 for k,v in data.model_dump().items():setattr(r,k,v)
 s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'班次编号重复')
 return r

def save_subscription(s,data,i=None):
 r=s.get(Subscription,i) if i else Subscription();new=i is None
 if not r:raise HTTPException(404,'订阅不存在')
 values=data.model_dump();first=values.pop('first_due_at')
 for k,v in values.items():setattr(r,k,v)
 # Explicit edit schedules the next future run; an initial override is for a first/catch-up delivery.
 r.next_run_at=first or next_due(r.daily_at,now_utc()).isoformat()
 s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'订阅名称重复')
 return r

def get_receipt(s,i):
 r=s.get(Receipt,i)
 if not r:raise HTTPException(404,'回执不存在')
 return r

def get_load_batch(s,i):
 r=s.get(LoadBatch,i)
 if not r:raise HTTPException(404,'配载批次不存在')
 return r

def save_load_batch(s,data,user,i=None):
 r=s.get(LoadBatch,i) if i else LoadBatch();new=i is None
 if not r:raise HTTPException(404,'配载批次不存在')
 if not new:
  # 与 worker 的入箱事务串行化：行锁等待占位/入箱完成后再判定状态
  r=s.query(LoadBatch).filter_by(id=i).with_for_update().first()
 if not new and r.state=='loaded':raise HTTPException(409,'批次已入箱，配载方案随晨报回执冻结，不能修订')
 codes=[l.code for l in data.lots]+[o.code for o in data.options]
 known={a.code:a for a in s.query(Arrival).filter(Arrival.code.in_(codes)).all()}
 for c in codes:
  a=known.get(c)
  if not a:raise HTTPException(422,'班次 '+c+' 不存在，请先在到发台账录入')
  if a.station!=data.station:raise HTTPException(422,'班次 '+c+' 属于'+a.station+'，不属于'+data.station)
 now=now_utc()
 if new:
  r.created_by=user.email;r.created_at=now.isoformat();r.stale_note='首次计算'
 else:
  s.query(CargoLot).filter_by(batch_id=r.id).delete();s.query(OutboundOption).filter_by(batch_id=r.id).delete();r.stale_note='批次修订，等待重算'
 r.station=data.station;r.business_day=data.business_day.isoformat();r.state='pending'
 s.add(r)
 try:
  s.flush()
  for l in data.lots:s.add(CargoLot(batch_id=r.id,code=l.code,volume=l.volume,note=l.note))
  for o in data.options:s.add(OutboundOption(batch_id=r.id,code=o.code,capacity=o.capacity,min_transfer=o.min_transfer))
  s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'该港站业务日已存在配载批次，请修订原批次')
 return r
