const number=value=>Number(value).toLocaleString('vi-VN',{maximumFractionDigits:1});
const dayLabel=day=>new Date(day+'T12:00:00Z').toLocaleDateString('vi-VN',{weekday:'short',day:'2-digit',month:'2-digit',timeZone:'UTC'});
const issuedLabel=stamp=>new Date(stamp).toLocaleString('vi-VN',{timeZone:'America/Los_Angeles'});
export function validateLive(data){
  if(data.schemaVersion!==1||data.timezone!=='America/Los_Angeles'||data.target!=='medic-dispatches'||data.unit!=='dispatches'||data.timeField!=='dispatch_dttm'||data.identityField!=='rowid'||!Number.isFinite(Date.parse(data.generatedAt))||data.rows?.length!==168||data.days?.length!==7)throw Error('Chưa có bản dự báo đúng đơn vị lượt điều động.');
  const times=new Set();
  for(const row of data.rows){if(!/^\d{4}-\d{2}-\d{2}T\d{2}:00:00$/.test(row.time)||times.has(row.time)||!Number.isFinite(row.prediction)||row.prediction<0)throw Error('Chuỗi dự báo chưa hợp lệ.');times.add(row.time);}
  for(const day of data.days){if(!/^\d{4}-\d{2}-\d{2}$/.test(day.date)||!Number.isFinite(day.prediction)||day.prediction<0||data.rows.filter(r=>r.time.startsWith(day.date)).length!==24)throw Error('Ngày dự báo chưa hợp lệ.');}
  return data;
}
export function installLiveForecast(){
  const $=selector=>document.querySelector(selector);
  const status=$('#live-status'),source=$('#live-source'),days=$('#live-days'),refresh=$('#live-refresh');
  let data,selected,lastLoaded=0;
  function showDay(date){
    selected=date;days.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.day===date)));
    const rows=data.rows.filter(row=>row.time.startsWith(date));
    $('#live-hourly').hidden=false;$('#live-day-title').textContent=dayLabel(date)+' · '+number(rows.reduce((sum,row)=>sum+row.prediction,0))+' lượt điều động dự báo';
    const chart=$('#live-chart');chart.replaceChildren();const max=Math.max(1,...rows.map(row=>row.prediction));
    for(const row of rows){const item=document.createElement('div');item.className='live-bar';item.title=row.time.slice(11,16)+' · '+number(row.prediction)+' lượt điều động';const bar=document.createElement('span');bar.style.height=(row.prediction/max*150)+'px';const label=document.createElement('small');label.textContent=row.time.slice(11,13);item.append(bar,label);chart.append(item);}
    chart.setAttribute('role','img');chart.setAttribute('aria-label','Dự báo theo giờ ngày '+dayLabel(date)+'. Số liệu đầy đủ trong bảng bên dưới.');
    const table=document.createElement('table');table.className='ops-table';
    const head=document.createElement('thead');const tr=document.createElement('tr');for(const title of ['Giờ San Francisco','Lượt điều động dự báo']){const th=document.createElement('th');th.scope='col';th.textContent=title;tr.append(th);}head.append(tr);table.append(head);
    const body=document.createElement('tbody');for(const row of rows){const tr=document.createElement('tr');for(const value of [row.time.slice(11,16),number(row.prediction)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);}table.append(body);$('#live-hour-table').replaceChildren(table);
  }
  async function load(){
    refresh.disabled=true;
    try{
      const response=await fetch('/api/live-forecast');if(!response.ok)throw Error('Chưa có dự báo cập nhật. Bản kết quả sẽ xuất hiện sau lần đồng bộ thành công.');
      const next=validateLive(await response.json());data=next;lastLoaded=Date.now();
      const stale=Date.now()-Date.parse(data.generatedAt)>36*3600000;
      status.textContent=(stale?'Kết quả đã cũ · ':data.refresh?.ok===false?'Lần cập nhật gần nhất chưa thành công · ':'Đã cập nhật · ')+issuedLabel(data.generatedAt)+' (San Francisco)';
      source.textContent='Dữ liệu quan sát đến '+data.observedThrough.replace('T',' ')+' · Bản ghi nguồn mới nhất '+data.sourceLatest.replace('T',' ')+'.';
      $('#live-model').textContent=data.model+' · Huấn luyện lại mỗi ngày trên '+number(data.trainingHours/24)+' ngày hoàn chỉnh. MAE kiểm tra trên 14 ngày lịch sử giữ riêng: '+number(data.validation.mae)+' lượt điều động/giờ; không phải độ chính xác đã kiểm chứng cho 7 ngày tương lai.';
      days.replaceChildren();for(const day of data.days){const button=document.createElement('button');button.type='button';button.dataset.day=day.date;button.className='live-day';const label=document.createElement('span');label.textContent=dayLabel(day.date);const value=document.createElement('strong');value.textContent=number(day.prediction);const unit=document.createElement('small');unit.textContent='lượt điều động / ngày';const peak=document.createElement('small');peak.textContent='Đỉnh '+day.peakHour;button.append(label,value,unit,peak);button.addEventListener('click',()=>showDay(day.date));days.append(button);}
      showDay(data.days.some(day=>day.date===selected)?selected:data.days[0].date);
    }catch(error){status.textContent=error.message+(data?' Đang giữ kết quả đã tải trước đó.':'');}
    finally{refresh.disabled=false;}
  }
  refresh.addEventListener('click',load);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastLoaded>15*60000)load();});
  load();
}
