import {MODELS,metrics,filterRows,capacity,replay,blocks,csv,validateDataset} from './analysis.mjs';
import {timeChart,heatmap} from './charts.mjs';

const $=s=>document.querySelector(s);
const fmt=(v,n=0)=>v===null||v===undefined?'—':Number(v).toLocaleString('vi-VN',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shortDate=t=>t.slice(8,10)+'/'+t.slice(5,7);
const dateTime=t=>shortDate(t)+' '+t.slice(11,16);
const sum=(rows,key)=>rows.reduce((s,r)=>s+r[key],0);
const state={page:'overview',model:'prophet',start:'',end:'',forecastMode:'replay',cursor:12,evaluation:'selected',fleet:16,minutes:60,utilization:.75,tablePage:0};
let dataset,cleanups=[],toastTimer;
const titles={overview:['Diễn biến nhu cầu cấp cứu','Đối chiếu số cuộc gọi thực tế và dự báo để nhận diện những giờ cần chú ý.'],forecast:['Dự báo nhu cầu theo giờ','Kiểm tra dự báo, dữ liệu quan sát và mức sai lệch trên cùng trục thời gian.'],capacity:['Lập kế hoạch năng lực','Khảo sát số xe cần thiết theo dự báo và các giả định phục vụ.']};

function notify(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,3000);}
function download(name,text,type='text/csv;charset=utf-8'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Đã chuẩn bị file tải xuống.');}
function selectedRows(){return filterRows(dataset.rows,state.start,state.end);}
function modelDescription(){return dataset.metadata.models[state.model];}
function legend(prediction=MODELS[state.model],planning=false){return `<div class="legend"><span class="legend-item"><span class="legend-line ${planning?'resource':''}"></span>${planning?'Xe ước tính':'Quan sát thực tế'}</span><span class="legend-item"><span class="legend-line ${planning?'capacity':'prediction'}"></span>${planning?'Xe hiện có':esc(prediction)}</span></div>`;}
function rail(items){return `<div class="summary-rail">${items.map(([label,value,unit='',detail=''])=>`<div class="summary-item"><span class="summary-label">${esc(label)}</span><strong class="summary-value">${value}<small>${esc(unit)}</small></strong>${detail?`<span class="summary-detail">${esc(detail)}</span>`:''}</div>`).join('')}</div>`;}
function chartSurface(title,note,id,{isCapacity=false,cursor=null}={}){return `<section class="chart-surface" aria-label="${esc(title)}"><div class="chart-heading"><div><h2>${title}</h2><p class="section-note">${note}</p></div>${legend(MODELS[state.model],isCapacity)}</div><div class="chart-wrap" id="${id}"></div><p class="chart-caption">${isCapacity?'Số xe được quy đổi từ nhu cầu dự báo, không phải số xe đã điều động.':cursor===null?'Di chuột hoặc dùng phím mũi tên trên biểu đồ để đọc từng mốc giờ.':'Vùng nền nhạt là thời gian chưa mở dữ liệu. Mỗi bước chỉ dự báo một giờ.'}</p>${cursor!==null?replayControls(cursor):''}</section>`;}
function observations(rows,{cursor=null}={}){const visible=cursor===null?null:replay(rows,cursor);return [{label:'Quan sát thực tế',color:'#376fad',value:(r,i)=>visible?visible[i].observed:r.actual},{label:MODELS[state.model],color:'#087e8b',dash:'6 4',value:(r,i)=>!visible||visible[i].predictionVisible?r[state.model]:null}];}
function drawDemand(host,rows,options={}){cleanups.push(timeChart($(host),rows,observations(rows,options),options));}
function table(headers,rows,{highlight=-1}={}){return `<div class="table-wrap"><table><thead><tr>${headers.map((h,i)=>`<th scope="col" class="${i?'number':''}">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map((r,i)=>`<tr ${i===highlight?'class="selected"':''}>${r.map((c,j)=>`<td class="${j?'number':''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
function eventTable(rows){return table(['Mốc giờ','Thực tế','Dự báo','Lệch'],rows.map(r=>[dateTime(r.time),fmt(r.actual),fmt(r[state.model],1),`<span class="${r.actual>r[state.model]?'risk-text':''}">${r.actual-r[state.model]>0?'+':''}${fmt(r.actual-r[state.model],1)}</span>`]));}
function dataExport(rows){return csv(rows,[{key:'time',label:'Mốc giờ CSV nguồn'},{key:'actual',label:'Cuộc gọi thực tế'},{key:'prophet',label:'Prophet'},{key:'lstm',label:'LSTM'},{key:'baseline',label:'Naive lag-1'}]);}
function overview(rows){
  const peak=rows.reduce((a,b)=>a.actual>=b.actual?a:b),m=metrics(rows,state.model),plan=capacity(rows,state.model,state),risk=plan.filter(r=>r.shortfall>0),riskPeriods=blocks(plan).sort((a,b)=>b.peak-a.peak).slice(0,3),worst=[...rows].sort((a,b)=>Math.abs(b.actual-b[state.model])-Math.abs(a.actual-a[state.model])).slice(0,5);
  $('#screen').innerHTML=rail([['Cuộc gọi quan sát',fmt(sum(rows,'actual')),'cuộc gọi'],['Dự báo '+MODELS[state.model],fmt(sum(rows,state.model),1),'cuộc gọi'],['Sai số trung bình',fmt(m.mae,2),'gọi/giờ'],['Vượt năng lực giả định',fmt(risk.length),'giờ',`${state.fleet} xe, ${state.minutes} phút/cuộc gọi, mức sử dụng ${fmt(state.utilization*100)}%`]])+
    `<div class="content-grid"><div>${chartSurface('Nhu cầu trong khoảng quan sát','Hậu kiểm theo từng giờ; đường nét đứt là dự báo từ mô hình.','overview-chart')}<div class="risk-periods"><strong>Vượt năng lực giả định</strong>${riskPeriods.length?riskPeriods.map(p=>`<span>${dateTime(p.start)}–${p.end.slice(11,16)} <b>thiếu tối đa ${p.peak} xe</b></span>`).join(''):'<span>Không có giờ vượt năng lực trong khoảng đang chọn.</span>'}</div></div><aside class="observation-aside" aria-label="Những giờ cần chú ý"><p class="aside-kicker">Giờ có nhiều cuộc gọi nhất</p><p class="peak-number">${peak.actual}<small>gọi/giờ</small></p><p class="aside-time">${dateTime(peak.time)}</p><ul class="event-list">${[...rows].sort((a,b)=>b.actual-a.actual).slice(0,3).map(r=>`<li><span class="event-time">${dateTime(r.time)}</span><strong>${r.actual} cuộc gọi</strong>; ${MODELS[state.model]} dự báo ${fmt(r[state.model],1)}.</li>`).join('')}</ul><a class="aside-link" href="#capacity">Khảo sát năng lực phục vụ</a></aside></div>
    <div class="lower-grid"><section><div class="section-heading"><h2>Nhịp nhu cầu trong tuần</h2></div><p class="section-note">Trung bình theo thứ và giờ trên toàn bộ tập test.</p><div id="overview-heatmap"></div><p class="section-note">Nhạt: ít cuộc gọi. Đậm: nhiều cuộc gọi. Số liệu tổng hợp toàn thành phố.</p></section><section><div class="section-heading"><h2>Những mốc lệch lớn</h2><span class="section-note">${MODELS[state.model]}</span></div>${eventTable(worst)}</section></div>
    <div class="notice"><p><strong>Phạm vi quan sát.</strong> Đây là hậu kiểm trên dữ liệu test, không phải luồng cấp cứu trực tiếp. Nguy cơ thiếu năng lực là kết quả của giả định; có thể điều chỉnh ở màn hình Kế hoạch năng lực.</p></div>`;
  drawDemand('#overview-chart',rows);heatmap($('#overview-heatmap'),dataset.rows);
}
function replayControls(cursor){return `<div class="replay-panel"><label for="replay-hour">Đã mở <strong>${cursor}</strong> / <span id="replay-total">24</span> giờ</label><button class="button" id="replay-reset">Bắt đầu lại</button><input id="replay-hour" type="range" min="0" max="24" value="${cursor}" aria-label="Số giờ thực tế đã mở"><button class="button button-primary" id="replay-next">Mở thêm một giờ</button></div>`;}
function forecast(rows){
  const date=rows[0].time.slice(0,10),day=rows.filter(r=>r.time.slice(0,10)===date),isReplay=state.forecastMode==='replay',cursor=Math.min(state.cursor,day.length),chartRows=isReplay?day:rows,description=modelDescription(),point=cursor<day.length?day[cursor]:null;
  const summary=isReplay?rail([['Thực tế đã mở',fmt(sum(day.slice(0,cursor),'actual')),'cuộc gọi'],['Giờ đang dự báo',point?point.time.slice(11,16):'Kết thúc',''],['Dự báo giờ đang xét',point?fmt(point[state.model],1):'—','cuộc gọi'],['Quan sát giờ đang xét',point?'Chưa mở':'Đã mở','']]):rail([['Giờ đánh giá',fmt(rows.length),'giờ'],['MAE',fmt(metrics(rows,state.model).mae,3),'gọi/giờ'],['RMSE',fmt(metrics(rows,state.model).rmse,3),'gọi/giờ'],['WAPE',fmt(metrics(rows,state.model).wape,2),'%']]);
  $('#screen').innerHTML=`<div class="mode-controls"><div class="segmented" role="group" aria-label="Chế độ dự báo"><button data-mode="replay" aria-pressed="${isReplay}">Phát lại một giờ</button><button data-mode="assessment" aria-pressed="${!isReplay}">Hậu kiểm đầy đủ</button></div><span class="mode-detail">${isReplay?'Phát lại ngày '+shortDate(date)+'; không mở dữ liệu thực tế ở phía trước.':'Đối chiếu toàn bộ khoảng đang chọn.'}</span></div>`+summary+
    `<div class="content-grid"><div>${chartSurface(isReplay?'Lịch sử và giờ dự báo kế tiếp':'Thực tế và kết quả dự báo',isReplay?'Lịch sử đã mở được vẽ liền; dự báo của giờ kế tiếp được vẽ nét đứt.':'Kết quả từng giờ sử dụng lịch sử thực tế trước giờ đó.','forecast-chart',{cursor:isReplay?cursor:null})}</div><aside class="observation-aside"><div><p class="aside-kicker">Mô hình đang sử dụng</p><h2>${MODELS[state.model]}</h2><p class="model-description">${esc(description.description)}</p><dl class="model-definition"><div><dt>Đầu vào</dt><dd>${esc(description.input)}</dd></div><div><dt>Dữ liệu train kết thúc</dt><dd>31/12/2024, 23:00</dd></div><div><dt>Chọn cấu hình</dt><dd>Validation năm 2025</dd></div><div><dt>Khoảng bất định</dt><dd>Chưa được cung cấp hoặc kiểm định.</dd></div></dl></div></aside></div>
    <section class="evaluation-section"><div class="evaluation-heading"><div><h2>Hiệu suất trên cùng mốc thời gian</h2><p class="section-note">MAE, RMSE và WAPE thấp hơn là tốt hơn.</p></div><label class="field-label" for="evaluation-scope">Phạm vi đánh giá <select id="evaluation-scope"><option value="selected" ${state.evaluation==='selected'?'selected':''}>Khoảng đang chọn</option><option value="all" ${state.evaluation==='all'?'selected':''}>Toàn bộ 6.772 giờ test</option></select></label></div><div id="model-scores"></div><p class="section-note">WAPE = tổng sai số tuyệt đối / tổng cuộc gọi thực tế. Hai mô hình có độ trễ đầu vào khác nhau; xem Dữ liệu & phương pháp.</p></section>
    <section class="forecast-data"><div class="section-heading"><h2>Bảng dự báo theo thời gian</h2><button id="download-forecast" class="text-button">Tải CSV ${isReplay?'các giờ đã mở':''}</button></div><div id="forecast-table"></div></section>`;
  drawDemand('#forecast-chart',chartRows,{cursor:isReplay?cursor:null});
  drawScores(rows,isReplay?day.slice(0,cursor):null);
  const visibleRows=isReplay?day.slice(0,Math.min(cursor+1,day.length)):rows;
  renderForecastTable(visibleRows,isReplay?cursor:null);
  document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{state.forecastMode=b.dataset.mode;state.tablePage=0;render();});
  $('#evaluation-scope').onchange=e=>{state.evaluation=e.target.value;drawScores(rows,isReplay?day.slice(0,cursor):null);};
  if(isReplay){$('#replay-total').textContent=day.length;$('#replay-next').disabled=cursor>=day.length;$('#replay-reset').onclick=()=>{state.cursor=0;render();};$('#replay-next').onclick=()=>{state.cursor=Math.min(day.length,cursor+1);render();};$('#replay-hour').max=day.length;$('#replay-hour').onchange=e=>{state.cursor=Number(e.target.value);render();};}
  $('#download-forecast').onclick=()=>download('ems-forecast.csv',dataExport(isReplay?day.slice(0,cursor):rows));
}
function drawScores(rows,revealed=null){
  const scope=state.evaluation==='all'?dataset.rows:(revealed??rows);
  const scored=Object.keys(MODELS).map(key=>({key,...metrics(scope,key)}));
  $('#model-scores').innerHTML=table(['Mô hình','MAE (gọi/giờ)','RMSE (gọi/giờ)','WAPE (%)'],scored.map(r=>[`<span class="model-name">${MODELS[r.key]}</span>`,fmt(r.mae,3),fmt(r.rmse,3),fmt(r.wape,2)]),{highlight:scored.findIndex(r=>r.key===state.model)})+`<p class="section-note">${fmt(scope.length)} giờ ${state.evaluation==='all'?'trong toàn bộ tập test':revealed?'đã mở ở ngày phát lại':'trong khoảng đang chọn'}. ${!scope.length?'Mở thêm một giờ để tính sai số.':''}</p>`;
}
function renderForecastTable(rows,cursor){
  const pageSize=12,maxPage=Math.max(0,Math.ceil(rows.length/pageSize)-1);state.tablePage=Math.min(state.tablePage,maxPage);
  const start=state.tablePage*pageSize;
  $('#forecast-table').innerHTML=table(['Mốc giờ','Quan sát','Dự báo '+MODELS[state.model],'Sai số tuyệt đối'],rows.slice(start,start+pageSize).map((r,i)=>{const known=cursor===null||i+start<cursor;return [dateTime(r.time),known?fmt(r.actual):'Chưa mở',fmt(r[state.model],2),known?fmt(Math.abs(r.actual-r[state.model]),2):'—'];}))+`<div class="table-actions"><span class="section-note">${rows.length?start+1:0}–${Math.min(start+pageSize,rows.length)} / ${fmt(rows.length)} giờ</span><div><button class="button button-quiet" id="table-prev" ${!state.tablePage?'disabled':''}>Trước</button><button class="button button-quiet" id="table-next" ${state.tablePage>=maxPage?'disabled':''}>Tiếp</button></div></div>`;
  $('#table-prev').onclick=()=>{state.tablePage--;renderForecastTable(rows,cursor);};$('#table-next').onclick=()=>{state.tablePage++;renderForecastTable(rows,cursor);};
}
function assumption(label,id,value,unit,min,max,step){return `<div class="assumption-field"><div class="assumption-header"><label for="${id}">${label}</label><output for="${id}" id="${id}-value">${value} ${unit}</output></div><input id="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"><div class="range-ends"><span>${min} ${unit}</span><span>${max} ${unit}</span></div></div>`;}
function capacityPage(rows){
  $('#screen').innerHTML=`<div class="capacity-layout"><aside class="assumptions" aria-label="Giả định năng lực"><h2>Giả định phục vụ</h2><p class="section-note">Một xe cho mỗi cuộc gọi. Chưa có dữ liệu ca trực hoặc thời gian phục vụ thực tế.</p>${assumption('Số xe hiện có','fleet',state.fleet,'xe',0,60,1)}${assumption('Thời gian phục vụ','minutes',state.minutes,'phút',15,180,15)}${assumption('Mức sử dụng mục tiêu','utilization',Math.round(state.utilization*100),'%',40,95,5)}<details><summary>Cách quy đổi nhu cầu</summary><p class="formula">Số xe = làm tròn lên [cuộc gọi dự báo × (phút phục vụ / 60) / mức sử dụng mục tiêu].</p><p class="formula">Đây là ước tính tải công việc, chưa xét vị trí, thời gian di chuyển, hàng đợi hoặc nhiều xe cho một cuộc gọi.</p></details></aside><div id="capacity-results" aria-live="polite"></div></div>`;
  for(const id of ['fleet','minutes','utilization'])$('#'+id).oninput=e=>{state[id]=Number(e.target.value)/(id==='utilization'?100:1);$('#'+id+'-value').textContent=e.target.value+' '+(id==='fleet'?'xe':id==='minutes'?'phút':'%');drawCapacity(rows);};
  drawCapacity(rows);
}
let capacityCleanup=null;
function drawCapacity(rows){
  if(capacityCleanup)capacityCleanup();capacityCleanup=null;
  const result=capacity(rows,state.model,state),short=result.filter(r=>r.shortfall>0),peak=result.reduce((a,b)=>a.required>=b.required?a:b),periods=blocks(result),maxShort=Math.max(...result.map(r=>r.shortfall));
  $('#capacity-results').innerHTML=`<div class="capacity-conclusion"><strong class="${short.length?'risk-text':''}">${fmt(short.length)} giờ</strong><span>${short.length?'có nhu cầu xe ước tính vượt số xe hiện có.':'nằm trong năng lực giả định đang chọn.'}</span></div><div class="capacity-facts"><span>Nhu cầu xe cao nhất: <strong>${peak.required} xe</strong></span><span>Thiếu lớn nhất: <strong>${maxShort} xe</strong></span><span>Nguồn dự báo: <strong>${MODELS[state.model]}</strong></span></div>${chartSurface('Nhu cầu xe và năng lực hiện có','Kịch bản giả định; không phải số xe đang vận hành thực tế.','capacity-chart',{isCapacity:true})}
    <section class="capacity-table"><div class="section-heading"><h2>Khoảng vượt năng lực giả định</h2><button class="text-button" id="download-capacity">Tải kịch bản CSV</button></div>${periods.length?table(['Bắt đầu','Kết thúc','Số giờ','Thiếu lớn nhất'],periods.slice(0,12).map(p=>[dateTime(p.start),dateTime(p.end),p.hours,p.peak+' xe'])):'<p class="section-note">Không có giờ vượt năng lực theo giả định hiện tại.</p>'}<p class="section-note">${periods.length>12?`Hiển thị 12 / ${periods.length} khoảng. CSV chứa toàn bộ giờ.`:'Các giờ liên tiếp được gộp thành một khoảng.'}</p></section>
    <div class="notice ${short.length?'risk':''}"><p><strong>Chênh lệch cần khảo sát.</strong> ${maxShort?`Theo các giả định này, giờ ${dateTime(peak.time)} cần thêm ${maxShort} xe để bằng tải công việc ước tính.`:'Số xe hiện có đủ đáp ứng tải công việc ước tính trong khoảng đã chọn.'} Chưa đủ dữ liệu để đề xuất phân bổ xe theo trạm hoặc ca trực thực tế.</p></div>`;
  capacityCleanup=timeChart($('#capacity-chart'),result,[{label:'Xe ước tính',color:'#087e8b',value:r=>r.required}],{unit:'Số xe theo giả định',limit:state.fleet,height:300});
  $('#download-capacity').onclick=()=>download('ems-capacity-scenario.csv',csv(result.map(r=>({...r,model:MODELS[state.model],minutes:state.minutes,utilizationPercent:state.utilization*100})),[{key:'time',label:'Mốc giờ'},{key:'model',label:'Mô hình'},{key:state.model,label:'Cuộc gọi dự báo'},{key:'minutes',label:'Phục vụ trung bình (phút)'},{key:'utilizationPercent',label:'Mức sử dụng mục tiêu (%)'},{key:'required',label:'Xe ước tính'},{key:'available',label:'Xe hiện có giả định'},{key:'shortfall',label:'Chênh lệch xe'}]));
}
function render(){
  cleanups.forEach(f=>f());cleanups=[];if(capacityCleanup){capacityCleanup();capacityCleanup=null;}
  const rows=selectedRows();if(!rows.length){$('#filter-message').textContent='Không có dữ liệu trong khoảng này. Chọn một khoảng trong tập test.';return;}
  const title=titles[state.page];$('#page-title').textContent=title[0];$('#page-description').textContent=title[1];
  document.title=title[0]+' | EMSForecast';$('#period-stamp').textContent=`${shortDate(rows[0].time)} – ${shortDate(rows.at(-1).time)} / 2026`;
  document.querySelectorAll('[data-page]').forEach(a=>{if(a.dataset.page===state.page)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  ({overview,forecast,capacity:capacityPage})[state.page](rows);
}
function methodDialog(){
  const m=dataset.metadata;
  $('#method-content').innerHTML=`<p>Dữ liệu EMS San Francisco đã tổng hợp theo giờ. Bản demo hiển thị kết quả suy luận từ checkpoint trên tập test; không thu thập dữ liệu trực tiếp và không huấn luyện lại trong trình duyệt.</p><h3>Phạm vi dữ liệu</h3><p>Train 2019–2024, validation 2025, test 2026. Đối chiếu ${fmt(m.count)} giờ từ ${dateTime(m.start)} đến ${dateTime(m.end)}. ${esc(m.timeConvention)}</p><h3>Cách đọc dự báo</h3><p>Prophet và LSTM tạo dự báo từng giờ với lịch sử trước giờ đó. Chế độ phát lại chỉ mở thêm một quan sát mỗi bước, không mô phỏng một dự báo nhiều ngày từ một cutoff.</p><p>LSTM giữ cách tạo sequence gốc, nên target mới nhất trong features tới t−2. Prophet nhận lag tới t−1. Hai mô hình có cùng giờ đánh giá nhưng thông tin đầu vào chưa hoàn toàn tương đương.</p><h3>Sai số và độ bất định</h3><p>MAE là sai số tuyệt đối trung bình. RMSE phạt mạnh sai số lớn. WAPE = tổng sai số tuyệt đối / tổng số cuộc gọi thực tế × 100%; không xác định khi tổng thực tế bằng 0. Bản demo chưa có khoảng dự báo bất định đã được kiểm định. ARIMA chưa được triển khai.</p><h3>Kịch bản năng lực</h3><p>Số xe là kết quả ước tính từ các giả định, không phải số xe đã điều động hoặc khuyến nghị vận hành. Chưa có số liệu nhân lực, vị trí trạm, thời gian phục vụ và quãng đường thực tế để tối ưu phân bổ.</p><button class="button" id="download-metadata">Tải thông tin nguồn dữ liệu</button>`;
  $('#download-metadata').onclick=()=>download('emsforecast-metadata.json',JSON.stringify(m,null,2),'application/json');
  $('#method-dialog').showModal();
}
async function init(){
  try {
    const response=await fetch('/api/dataset');if(!response.ok)throw new Error('Chưa có bộ kết quả để hiển thị.');
    dataset=validateDataset(await response.json());
    state.start='2026-01-15';state.end=state.start;if(!dataset.rows.some(r=>r.time.startsWith(state.start)))state.start=state.end=dataset.rows[0].time.slice(0,10);
    for(const id of ['start-date','end-date']){$('#'+id).min=dataset.metadata.start.slice(0,10);$('#'+id).max=dataset.metadata.end.slice(0,10);}
    $('#start-date').value=state.start;$('#end-date').value=state.end;
    $('#app-status').hidden=true;$('#workspace').hidden=false;
    state.page=Object.hasOwn(titles,location.hash.slice(1))?location.hash.slice(1):'overview';
    render();
    $('#filters').onsubmit=e=>{e.preventDefault();const start=$('#start-date').value,end=$('#end-date').value;if(start>end){$('#filter-message').textContent='Ngày bắt đầu cần trước hoặc bằng ngày kết thúc.';return;}if(!filterRows(dataset.rows,start,end).length){$('#filter-message').textContent='Khoảng này chưa có dữ liệu. Hãy chọn ngày trong tập test.';return;}state.start=start;state.end=end;state.tablePage=0;state.cursor=12;$('#filter-message').textContent='';render();};
    $('#full-period').onclick=()=>{state.start=dataset.metadata.start.slice(0,10);state.end=dataset.metadata.end.slice(0,10);$('#start-date').value=state.start;$('#end-date').value=state.end;state.tablePage=0;$('#filter-message').textContent='';render();};
    $('#model-select').onchange=e=>{if(!dataset.metadata.models[e.target.value]?.available)return;state.model=e.target.value;render();};
    addEventListener('hashchange',()=>{state.page=Object.hasOwn(titles,location.hash.slice(1))?location.hash.slice(1):'overview';state.tablePage=0;render();window.scrollTo({top:0,behavior:'instant'});});
    $('#method-button').onclick=methodDialog;$('#close-method').onclick=()=>$('#method-dialog').close();
  } catch(error) {
    $('#workspace').hidden=true;$('#app-status').hidden=false;
    $('#app-status').setAttribute('role','alert');$('#app-status').innerHTML=`<div class="error-message"><h2>Chưa thể mở dữ liệu demo</h2><p>${esc(error.message)}</p><p>Chạy <code>python -m ems.web.export</code> trong môi trường mô hình rồi khởi động lại web.</p><button class="button" id="retry-load">Thử tải lại</button></div>`;$('#retry-load').onclick=()=>location.reload();
  }
}
init();
