import {state} from '../stores/session.js';import {table} from '../components/common/table.js';import {field,select} from '../components/common/fields.js';import {STATIONS,LOAD_LABELS} from '../constants/enums.js';import {esc} from '../utils/html.js';import {local} from '../utils/dates.js';
export function payload(d){
 let rows=(text,n,label)=>(text||'').split('\n').map(x=>x.trim()).filter(Boolean).map((line,k)=>{let c=line.split(/[,，\s]+/).filter(Boolean);if(c.length!==n)throw Error(label+'第'+(k+1)+'行应为'+n+'列：'+line);return c});
 let lots=rows(d.lots,2,'进站货量').map(([code,volume])=>({code,volume:Number(volume)}));
 let options=rows(d.options,3,'出港候选').map(([code,capacity,min_transfer])=>({code,capacity:Number(capacity),min_transfer:Number(min_transfer)}));
 if(!lots.length||!options.length)throw Error('至少录入一条进站货量和一条出港候选');
 if(lots.some(l=>!(l.volume>0)))throw Error('货量必须为正数');
 if(options.some(o=>!(o.capacity>0)||!(Number.isInteger(o.min_transfer)&&o.min_transfer>=0)))throw Error('舱位必须为正数，最短换装为不小于0的整数分钟');
 return {station:d.station,business_day:d.business_day,lots,options}
}
function detail(d){
 let p=d.plan;
 return `<p><span class="tag">${LOAD_LABELS[d.state]||esc(d.state)}</span>${d.stale_note?` <span class="tag">${esc(d.stale_note)}</span>`:''}${d.revision?` <span class="tag">重算 ${d.revision} 次</span>`:''}</p>
 ${p?`<div class="metrics"><div><strong>${p.summary.allocated_volume} / ${p.summary.total_volume}</strong>已配 / 总货量（吨）</div><div><strong>${p.summary.total_wait_minutes}</strong>货量加权等待（吨·分）</div><div><strong>${p.summary.allocation_count}</strong>分配笔数</div></div>
 <h3>分配明细</h3>${table(['进站班次','出港班次','货量(吨)','实际到','实际发','等待(分)'],p.allocations.map(a=>[a.lot_code,a.option_code,a.volume,local(a.arrival_at),local(a.departure_at),a.wait_minutes]))}
 <h3>未配货量与原因</h3>${table(['进站班次','未配货量(吨)','原因'],p.unallocated.map(u=>[u.lot_code,u.volume,u.reason]))}
 <h3>候选与来源</h3>${table(['出港班次','舱位(吨)','最短换装(分)','本批可用(吨)','台账实际发'],p.inputs.options.map(o=>[o.code,o.capacity,o.min_transfer,o.available,local(o.departure_at)]))}
 <p class="notice">算法 ${esc(p.version)} · 指纹 ${esc((d.fingerprint||'').slice(0,20))}… · 计算于 ${local(p.computed_at)}<br>接续只按台账实际到发计算；其他已入箱批次占用：${Object.entries(p.inputs.occupied_by_others).map(([k,v])=>esc(k)+' '+v+'吨').join('，')||'无'}。${d.history&&d.history.length?`保留 ${d.history.length} 份被替换的过期方案。`:''}${d.receipt_id?`随晨报回执 #${d.receipt_id} 入箱于 ${local(d.loaded_at)}，舱位占用已生效。`:'尚未入箱：占位不扣减共享舱位，入箱前若台账修订或他批占用变化将拒绝入箱并重算。'}</p>`
 :'<p class="notice">待计算：worker 每秒扫描待计算批次并完成占位。</p>'}
 ${d.state!=='loaded'?`<form id="recompute"><button>重新计算占位</button></form>`:'<p class="notice">已入箱，方案随回执冻结，不能修订或重算。</p>'}`
}
export function render(){
 let d=state.loadDetail;
 return `<div class="split"><section class="panel"><h2>${d?'批次 #'+d.id+' · '+esc(d.station)+' · '+esc(d.business_day):'单班准点，也可能错过接驳'}</h2>${d?detail(d):'<p class="notice">在右侧选择批次查看方案，或发起新批次。配载只按实际到发计算：进站未到发暂不配，出港未发暂不作候选。先使接续总货量最大，再使货量加权总等待最小；可拆货，共享舱位不超卖。占位方案随晨报回执入箱生效，重叠订阅复用同一份配载，不重复占用。</p>'}</section><aside class="side"><h2>配载批次</h2>${state.loads.map(b=>`<button class="study" data-load="${b.id}">#${b.id} ${esc(b.business_day)} ${esc(b.station)}<br>${LOAD_LABELS[b.state]||esc(b.state)} · 已配 ${b.allocated_volume??'—'}/${b.total_volume??'—'} 吨</button>`).join('')||'<p>尚无批次，请在下方发起。</p>'}<h2>发起 / 修订批次</h2><form id="loadbatch">${field('批次ID（修订时填）','record_id','number','min=1')}${select('港站','station',STATIONS.map(s=>[s,s]))}${field('业务日 / 上海','business_day','date',`required value="${state.context.yesterday}"`)}<label>进站货量（每行：班次编号,货量吨）<textarea name="lots" rows="4" required placeholder="LG-901,10"></textarea></label><label>出港候选（每行：班次编号,舱位吨,最短换装分钟）<textarea name="options" rows="4" required placeholder="LG-903,10,40"></textarea></label><button class="primary">保存并发起配载</button></form><p>班次须在到发台账中已录入且属于该港站。已入箱批次冻结；未入箱批次可修订，修订后回到待计算。</p></aside></div>`
}
