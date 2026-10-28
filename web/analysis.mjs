export const MODELS = {prophet:'Prophet',lstm:'LSTM',baseline:'Naive lag-1'};
export function metrics(rows,key) {
  if(!rows.length) return {mae:null,rmse:null,wape:null,bias:null};
  let absolute=0,squared=0,total=0,signed=0;
  for(const row of rows) {const e=row.actual-row[key];absolute+=Math.abs(e);squared+=e*e;total+=Math.abs(row.actual);signed+=e;}
  return {mae:absolute/rows.length,rmse:Math.sqrt(squared/rows.length),wape:total?absolute/total*100:null,bias:signed/rows.length};
}
export function filterRows(rows,start,end) {return rows.filter(r=>r.time.slice(0,10)>=start&&r.time.slice(0,10)<=end);}
export function capacity(rows,key,{fleet,minutes,utilization}) {
  if(!Number.isFinite(fleet)||fleet<0||!Number.isFinite(minutes)||minutes<=0||!Number.isFinite(utilization)||utilization<=0||utilization>1) throw new Error('Giả định năng lực không hợp lệ.');
  const factor=minutes/60/utilization;
  return rows.map(r=>({...r,required:Math.ceil(r[key]*factor),available:fleet,shortfall:Math.max(0,Math.ceil(r[key]*factor)-fleet)}));
}
export function replay(rows,cursor) {
  const end=Math.max(0,Math.min(rows.length,cursor));
  return rows.map((row,i)=>({...row,observed:i<end?row.actual:null,predictionVisible:i<=end}));
}
export function blocks(rows,key='shortfall') {
  const groups=[];
  for(const row of rows) {
    if(row[key]>0){const last=groups.at(-1);if(last&&new Date(row.time+'Z')-new Date(last.end+'Z')===3600000){last.end=row.time;last.hours++;last.peak=Math.max(last.peak,row[key]);}else groups.push({start:row.time,end:row.time,hours:1,peak:row[key]});}
  }
  return groups;
}
export function csv(rows,columns) {
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  return '\uFEFF'+[columns.map(c=>quote(c.label)).join(','),...rows.map(r=>columns.map(c=>quote(r[c.key])).join(','))].join('\r\n');
}
export function validateDataset(value) {
  if(value?.schemaVersion!==1||!Array.isArray(value.rows)||!value.rows.length) throw new Error('Bộ dữ liệu demo chưa đúng định dạng.');
  if(value.metadata?.count!==value.rows.length) throw new Error('Số giờ dữ liệu không khớp metadata.');
  let previous=null;
  for(const r of value.rows) {
    if(typeof r.time!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:00:00$/.test(r.time)) throw new Error('Mốc thời gian không hợp lệ.');
    const timestamp=Date.parse(r.time+'Z');
    if(!Number.isFinite(timestamp)||(previous!==null&&timestamp-previous!==3600000)) throw new Error('Dữ liệu cần liên tục theo từng giờ.');
    previous=timestamp;
    for(const k of ['actual','prophet','lstm','baseline'])if(!Number.isFinite(r[k])||r[k]<0)throw new Error('Dữ liệu có giá trị dự báo không hợp lệ.');
  }
  return value;
}
