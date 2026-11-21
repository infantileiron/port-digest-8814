from sqlalchemy import select
from src.models.entities import LoadBatch,CargoLot,OutboundOption,Arrival,Audit
from src.services import connection

def _inputs(s,batch):
 lots=[{'code':l.code,'volume':l.volume,'note':l.note}for l in s.query(CargoLot).filter_by(batch_id=batch.id).all()]
 options=[{'code':o.code,'capacity':o.capacity,'min_transfer':o.min_transfer}for o in s.query(OutboundOption).filter_by(batch_id=batch.id).all()]
 codes={l['code']for l in lots}|{o['code']for o in options}
 arrivals={}
 if codes:
  for a in s.query(Arrival).filter(Arrival.code.in_(codes)).all():arrivals[a.code]={'planned_at':a.planned_at,'actual_at':a.actual_at,'station':a.station}
 return lots,options,arrivals

def _occupied(s,batch,codes):
 # 只有已入箱批次才扣减共享舱位；占位不扣减。
 occ={c:0.0 for c in codes}
 others=s.query(LoadBatch).filter(LoadBatch.state=='loaded',LoadBatch.id!=batch.id).all()
 for b in others:
  for a in (b.plan or {}).get('allocations',[]):
   if a['option_code']in occ:occ[a['option_code']]+=a['volume']
 return occ

def _fingerprint(s,batch):
 lots,options,arrivals=_inputs(s,batch)
 occupied=_occupied(s,batch,[o['code']for o in options])
 return connection.fingerprint(batch.station,batch.business_day,lots,options,arrivals,occupied)

def compute_batch(s,batch,now,reason):
 lots,options,arrivals=_inputs(s,batch)
 occupied=_occupied(s,batch,[o['code']for o in options])
 plan=connection.build_plan(batch.station,batch.business_day,lots,options,arrivals,occupied,now.isoformat())
 if batch.plan is not None:
  history=list(batch.history or[])
  history.append({'reason':reason,'superseded_at':now.isoformat(),'fingerprint':batch.fingerprint,'plan':batch.plan})
  batch.history=history[-10:];batch.revision=(batch.revision or 0)+1
 batch.plan=plan;batch.fingerprint=plan['fingerprint'];batch.state='computed';batch.computed_at=now.isoformat();batch.stale_note=reason
 s.add(batch)
 return plan

def compute_pending(s,now):
 batches=s.scalars(select(LoadBatch).where(LoadBatch.state=='pending').with_for_update(skip_locked=True)).all()
 for b in batches:
  plan=compute_batch(s,b,now,b.stale_note or '首次计算')
  s.add(Audit(actor='scheduler',action='配载批次 %s 计算占位：已配 %s/%s 吨'%(b.id,plan['summary']['allocated_volume'],plan['summary']['total_volume']),created=now.isoformat()))
 s.commit()
 return[b.id for b in batches]

def resolve_for_receipt(s,station,day,receipt,now):
 # 晨报入箱时把对应港站/业务日的配载批次一并入箱；已入箱的重叠订阅复用同份方案，不重复占用。
 batch=s.query(LoadBatch).filter_by(station=station,business_day=day).with_for_update().first()
 if not batch:return None
 if batch.state=='loaded':
  s.add(Audit(actor='scheduler',action='回执 %s 复用配载批次 %s，不重复占用舱位'%(receipt.id,batch.id),created=now.isoformat()))
  return{'batch_id':batch.id,'station':station,'business_day':day,'reused':True,'plan':batch.plan}
 if batch.state=='pending':
  plan=compute_batch(s,batch,now,batch.stale_note or '首次计算')
 elif batch.fingerprint!=_fingerprint(s,batch):
  plan=compute_batch(s,batch,now,'台账修订或舱位占用变化：过期占位方案拒绝入箱，按最新台账重算')
  s.add(Audit(actor='scheduler',action='配载批次 %s 占位方案过期，拒绝入箱并重算'%batch.id,created=now.isoformat()))
 batch.state='loaded';batch.loaded_at=now.isoformat();batch.receipt_id=receipt.id
 s.add(batch)
 s.add(Audit(actor='scheduler',action='配载批次 %s 随晨报回执 %s 入箱，舱位占用生效'%(batch.id,receipt.id),created=now.isoformat()))
 return{'batch_id':batch.id,'station':station,'business_day':day,'reused':False,'plan':batch.plan}

def summary_view(b):
 plan=b.plan or{};sm=plan.get('summary')or{}
 return{'id':b.id,'station':b.station,'business_day':b.business_day,'state':b.state,'stale_note':b.stale_note,'revision':b.revision or 0,'receipt_id':b.receipt_id,'created_by':b.created_by,'created_at':b.created_at,'computed_at':b.computed_at,'loaded_at':b.loaded_at,'lot_count':sm.get('lot_count'),'option_count':sm.get('option_count'),'total_volume':sm.get('total_volume'),'allocated_volume':sm.get('allocated_volume'),'total_wait_minutes':sm.get('total_wait_minutes'),'unallocated_count':len(plan.get('unallocated')or[])if plan else None}
