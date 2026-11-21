import hashlib,json
from collections import deque
from src.utils.time import aware
VERSION='connection-mcmf-v1'
SCALE=1000
METHOD='最小费用最大流：先最大化接续总货量，再最小化货量加权总等待（吨·分）。货量可拆分到多个出港班次；共享舱位按已入箱批次扣减，不超卖。进站未到发的货量暂不配，出港未发的班次暂不作候选；等待=实际发−实际到。'

def _min_cost_max_flow(lot_caps,option_caps,edges):
 # 源->货量->候选->汇，整数流；每次沿最短路增广，得到最大流量中费用最小解。
 n,m=len(lot_caps),len(option_caps);N=n+m+2;SRC,SNK=0,N-1
 graph=[[]for _ in range(N)]
 def add(u,v,cap,cost):
  graph[u].append([v,cap,cost,len(graph[v])]);graph[v].append([u,0,-cost,len(graph[u])-1])
 for i,c in enumerate(lot_caps):add(SRC,1+i,c,0)
 refs=[]
 for i,j,cost in edges:
  add(1+i,1+n+j,lot_caps[i],cost);refs.append((i,j,1+i,len(graph[1+i])-1,lot_caps[i]))
 for j,c in enumerate(option_caps):add(1+n+j,SNK,c,0)
 INF=float('inf');flow=0;cost_total=0
 while True:
  dist=[INF]*N;prev=[None]*N;inq=[False]*N;dist[SRC]=0;q=deque([SRC]);inq[SRC]=True
  while q:
   u=q.popleft();inq[u]=False
   for k,e in enumerate(graph[u]):
    if e[1]>0 and dist[u]+e[2]<dist[e[0]]:
     dist[e[0]]=dist[u]+e[2];prev[e[0]]=(u,k)
     if not inq[e[0]]:q.append(e[0]);inq[e[0]]=True
  if prev[SNK] is None:break
  b=INF;v=SNK
  while v!=SRC:u,k=prev[v];b=min(b,graph[u][k][1]);v=u
  v=SNK
  while v!=SRC:
   u,k=prev[v];e=graph[u][k];e[1]-=b;graph[v][e[3]][1]+=b;v=u
  flow+=b;cost_total+=b*dist[SNK]
 used={}
 for i,j,u,k,cap in refs:
  gone=cap-graph[u][k][1]
  if gone>0:used[(i,j)]=gone
 return used,cost_total

def fingerprint(station,day,lots,options,arrivals,occupied):
 payload={'version':VERSION,'station':station,'business_day':day,
 'lots':sorted(({'code':l['code'],'volume':round(l['volume'],3)}for l in lots),key=lambda x:(x['code'],x['volume'])),
 'options':sorted(({'code':o['code'],'capacity':round(o['capacity'],3),'min_transfer':o['min_transfer']}for o in options),key=lambda x:x['code']),
 'arrivals':{c:[arrivals[c]['planned_at'],arrivals[c]['actual_at']]for c in sorted(arrivals)},
 'occupied':{k:round(v,3)for k,v in sorted(occupied.items())}}
 return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def build_plan(station,day,lots,options,arrivals,occupied,computed_at):
 # lots/options 为录入快照；arrivals 为台账快照；occupied 为其他已入箱批次对候选班次的占用。
 lot_states=[]
 for l in lots:
  a=arrivals.get(l['code']);arr=aware(a['actual_at'])if a and a['actual_at']else None
  lot_states.append({'code':l['code'],'volume':round(l['volume'],3),'arrival':arr,'arrival_at':a['actual_at']if a else None})
 option_states=[]
 for o in options:
  a=arrivals.get(o['code']);dep=aware(a['actual_at'])if a and a['actual_at']else None
  option_states.append({'code':o['code'],'capacity':round(o['capacity'],3),'min_transfer':o['min_transfer'],'departure':dep,'departure_at':a['actual_at']if a else None,'available':max(0.0,round(o['capacity']-occupied.get(o['code'],0.0),3))})
 edges=[];feasible={i:[]for i in range(len(lot_states))}
 for i,l in enumerate(lot_states):
  if l['arrival']is None:continue
  for j,o in enumerate(option_states):
   if o['departure']is None:continue
   wait=(o['departure']-l['arrival']).total_seconds()/60
   if wait+1e-9>=o['min_transfer']:
    edges.append((i,j,round(wait*SCALE)));feasible[i].append(j)
 used,cost=_min_cost_max_flow([round(l['volume']*SCALE)for l in lot_states],[round(o['available']*SCALE)for o in option_states],edges)
 allocations=[];per_lot=[0.0]*len(lot_states)
 for(i,j),units in sorted(used.items()):
  l,o=lot_states[i],option_states[j];volume=round(units/SCALE,3);wait=round((o['departure']-l['arrival']).total_seconds()/60,3)
  allocations.append({'lot_code':l['code'],'option_code':o['code'],'volume':volume,'arrival_at':l['arrival_at'],'departure_at':o['departure_at'],'wait_minutes':wait})
  per_lot[i]+=volume
 unallocated=[]
 for i,l in enumerate(lot_states):
  rest=round(l['volume']-per_lot[i],3)
  if rest<=0:continue
  if l['arrival']is None:reason='进站班次未到发，暂不配载'
  elif not feasible[i]:reason='无可接续出港班次：候选班次未发或不满足最短换装'
  else:reason='出港舱位不足，剩余货量暂挂'
  unallocated.append({'lot_code':l['code'],'volume':rest,'reason':reason})
 allocated=round(sum(a['volume']for a in allocations),3);total=round(sum(l['volume']for l in lot_states),3)
 summary={'total_volume':total,'allocated_volume':allocated,'unallocated_volume':round(total-allocated,3),'total_wait_minutes':round(cost/(SCALE*SCALE),3),'lot_count':len(lot_states),'option_count':len(option_states),'allocation_count':len(allocations)}
 inputs={'lots':[{'code':l['code'],'volume':l['volume']}for l in lot_states],
 'options':[{'code':o['code'],'capacity':o['capacity'],'min_transfer':o['min_transfer'],'available':o['available'],'departure_at':o['departure_at']}for o in option_states],
 'arrivals':{c:arrivals[c]for c in sorted(arrivals)},'occupied_by_others':{k:round(v,3)for k,v in sorted(occupied.items())}}
 plan={'version':VERSION,'station':station,'business_day':day,'algorithm':METHOD,'summary':summary,'allocations':allocations,'unallocated':unallocated,'inputs':inputs,'computed_at':computed_at}
 plan['fingerprint']=fingerprint(station,day,lots,options,arrivals,occupied)
 return plan
