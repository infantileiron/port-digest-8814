from sqlalchemy import Column,Integer,String,Float,JSON,Text,Boolean,ForeignKey,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True,nullable=False);password=Column(String(200));role=Column(String(20))
class Arrival(Base):
 __tablename__='arrivals'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);station=Column(String(30));planned_at=Column(String(40));actual_at=Column(String(40),nullable=True);note=Column(Text,default='')
class Subscription(Base):
 __tablename__='subscriptions'
 id=Column(Integer,primary_key=True);name=Column(String(100),unique=True,nullable=False);station=Column(String(30));daily_at=Column(String(5));recipient=Column(String(80));enabled=Column(Boolean,default=False);next_run_at=Column(String(40));last_run_at=Column(String(40),nullable=True)
class Receipt(Base):
 __tablename__='receipts'
 __table_args__=(UniqueConstraint('subscription_id','report_day',name='uq_receipt_subscription_day'),)
 id=Column(Integer,primary_key=True);subscription_id=Column(Integer,ForeignKey('subscriptions.id'));report_day=Column(String(10));recipient=Column(String(80));created_at=Column(String(40));state=Column(String(20),default='delivered');payload=Column(JSON);review_note=Column(Text,default='')
class LoadBatch(Base):
 __tablename__='load_batches'
 __table_args__=(UniqueConstraint('station','business_day',name='uq_loadbatch_station_day'),)
 id=Column(Integer,primary_key=True);station=Column(String(30));business_day=Column(String(10));state=Column(String(20),default='pending');plan=Column(JSON,nullable=True);fingerprint=Column(String(64),nullable=True);history=Column(JSON,default=list);revision=Column(Integer,default=0);stale_note=Column(Text,default='');receipt_id=Column(Integer,ForeignKey('receipts.id'),nullable=True);created_by=Column(String(100));created_at=Column(String(40));computed_at=Column(String(40),nullable=True);loaded_at=Column(String(40),nullable=True)
class CargoLot(Base):
 __tablename__='cargo_lots'
 id=Column(Integer,primary_key=True);batch_id=Column(Integer,ForeignKey('load_batches.id'));code=Column(String(60));volume=Column(Float);note=Column(Text,default='')
class OutboundOption(Base):
 __tablename__='outbound_options'
 id=Column(Integer,primary_key=True);batch_id=Column(Integer,ForeignKey('load_batches.id'));code=Column(String(60));capacity=Column(Float);min_transfer=Column(Integer)
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
