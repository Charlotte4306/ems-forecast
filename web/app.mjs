import {installReferenceMotion} from './reference-motion.mjs';
import {installZenlessShell} from './zenless.mjs';
import {screenFromLocation} from './routes.mjs';
import {installLiveForecast} from './live.mjs';
import {enhanceOperations} from './operations.mjs';
import {score,dayRows,validateProfiles} from './dashboard.mjs';
import {csv} from './analysis.mjs';

const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const fmt=(x,d=1)=>x===null?'—':Number(x).toLocaleString('vi-VN',{maximumFractionDigits:d});
const date=s=>s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4);
const short=s=>s.slice(8,10)+'/'+s.slice(5,7);
const text=(s,v)=>{const n=$(s);if(n)n.textContent=v;};
const section=(page,title)=>$$(`#screen-${page} section`).find(n=>n.querySelector('h2')?.textContent===title);
function sectionText(page,title,selector,value){const s=section(page,title);if(s?.querySelector(selector))s.querySelector(selector).textContent=value;}
function values(selector,list){$$(selector).forEach((n,i)=>{if(list[i]!==undefined)n.textContent=list[i];});}
function cellRows(host,headers,rows,grid){
  host.replaceChildren();host.setAttribute('aria-label',headers.join(', '));
  for(const [index,row] of [headers,...rows].entries()){
    const element=document.createElement('div');element.className=`trow ${index===0?'head ':''}${grid}`;element.setAttribute('role','row');
    row.forEach((value,i)=>{const cell=document.createElement('div');cell.className='tcell num';cell.setAttribute('role',index===0?'columnheader':'cell');cell.dataset.label=headers[i];cell.textContent=value;element.append(cell);});host.append(element);
  }
}
function unavailableChart(id,label){const node=document.getElementById(id);if(!node)return;node.replaceChildren();node.setAttribute('aria-label',label);const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x','560');t.setAttribute('y','120');t.setAttribute('text-anchor','middle');t.setAttribute('class','data-unavailable');t.textContent=label;node.append(t);}
let saved={density:'comfy',motion:false};
try{const old=JSON.parse(localStorage.getItem('emsforecast.reference-preferences'));if(old&&['comfy','compact'].includes(old.density)&&typeof old.motion==='boolean')saved=old;}catch{}
function restoreSettings(){
  document.body.classList.toggle('reduce-motion',saved.motion);document.body.classList.toggle('data-compact',saved.density==='compact');
  $$('#density-group .opt').forEach(n=>n.classList.toggle('sel',n.dataset.density===saved.density));
  $('#motion-switch').setAttribute('aria-checked',String(saved.motion));text('#motion-state',saved.motion?'Bật':'Tắt');
  $$('#preview-table .trow').forEach(n=>n.style.padding=saved.density==='compact'?'5px 0':'12px 0');
}
function saveSettings(){saved={density:$('#density-group .sel').dataset.density,motion:$('#motion-switch').getAttribute('aria-checked')==='true'};document.body.classList.toggle('data-compact',saved.density==='compact');try{localStorage.setItem('emsforecast.reference-preferences',JSON.stringify(saved));}catch{text('#set-status','Đã áp dụng; trình duyệt không cho lưu lâu dài.');}}

async function start(){
  const response=await fetch('/api/dataset');if(!response.ok)throw new Error('Không tải được dữ liệu. Kiểm tra máy chủ rồi tải lại trang.');
  const dataset=validateProfiles(await response.json());
  const query=new URLSearchParams(location.search),requestedProfile=query.get('profile')?.replaceAll('-','_'),key=Object.hasOwn(dataset.profiles,requestedProfile)?requestedProfile:(dataset.profiles.prophet_h24?'prophet_h24':'prophet_h1');
  const profile=dataset.profiles[key],all=profile.rows;
  let day=query.get('day')||'2026-09-29';if(!dayRows(profile,day).length)day=all[0].time.slice(0,10);
  const current=dayRows(profile,day),previousDate=new Date(day+'T00:00:00Z');previousDate.setUTCDate(previousDate.getUTCDate()-1);
  const previous=dayRows(profile,previousDate.toISOString().slice(0,10));
  const month=day.slice(0,7),history=all.filter(r=>r.time.startsWith(month)&&r.time.slice(0,10)<day);
  const context=history.length?history:all.filter(r=>r.time.slice(0,10)===day);
  const range=`${date(context[0].time)}–${date(context.at(-1).time)}`;
  const total=context.reduce((s,r)=>s+r.actual,0),days=new Set(context.map(r=>r.time.slice(0,10))).size;
  const forecastTotal=current.reduce((s,r)=>s+r.prediction,0),peak=current.reduce((a,b)=>b.prediction>a.prediction?b:a),metrics=score(all);
  const mode=profile.horizon===24?'24 giờ từ đầu ngày':'1 giờ, cập nhật từng giờ';
  const initialScreen=screenFromLocation(location);
  // Replace only labels and values inside the reference's original elements.
  $$('.page-foot').forEach(n=>n.textContent='EMSForecast · San Francisco · Đánh giá trên dữ liệu lịch sử · Thời gian theo dữ liệu nguồn');
  text('.side-context p:nth-child(2)','Đánh giá trên dữ liệu lịch sử');
  text('.side-context > div:last-child','Kết quả mô hình đã lưu');
  text('.side-footer > div:first-child','Bản demo học thuật · Dữ liệu thật');
  for(const p of ['tongquan','dubao','danhgia','lichsu']){
    text(`#screen-${p} > .banner .b-label`,'DỮ LIỆU LỊCH SỬ');
    text(`#screen-${p} > .banner .b-text`,`San Francisco · ${fmt(all.length,0)} giờ kiểm tra · Kết quả đã lưu, không phải dữ liệu thời gian thực`);
  }
  const control=$('#topbar-filters .control');control.replaceChildren();const input=document.createElement('input');input.type='date';input.value=day;input.min=all[0].time.slice(0,10);input.max=all.at(-1).time.slice(0,10);input.setAttribute('aria-label','Ngày dự báo');control.append(input);
  input.addEventListener('change',()=>{if(input.value){const url=new URL(location.href);url.searchParams.set('day',input.value);location.href=url.href;}});
  text('.freshness .num','Bản kết quả đã lưu');
  const overviewKpis=$$('#screen-tongquan .kpi');
  const kpiData=[[fmt(total,0)+' lượt',`${range} · ${context.length} giờ`,total,' lượt',0],[fmt(total/days)+' lượt/ngày',`Trung bình ${days} ngày có dữ liệu`,total/days,' lượt/ngày',1],['— phút','Chưa đóng gói dữ liệu thời gian xe bận',null,'',0],[fmt(forecastTotal)+' lượt',`${date(day)} · ${mode}`,forecastTotal,' lượt',1]];
  overviewKpis.forEach((n,i)=>{const [value,note,count,suffix,decimals]=kpiData[i],v=n.querySelector('.k-value');v.textContent=value;v.removeAttribute('data-count');if(count!==null){v.dataset.count=count;v.dataset.suffix=suffix;v.dataset.decimals=decimals;}n.querySelector('.k-note').textContent=note;});
  const before=previous.length?short(previous[0].time):'Không có ngày trước';
  const trendText=`Lượt/giờ · Quan sát ${before} và dự báo ${short(day)} · ${profile.name} · ${mode}`;
  for(const [p,title] of [['tongquan','Xu hướng lượt điều động'],['dubao','Lượt điều động quan sát và dự báo']]){
    sectionText(p,title,'.sub',trendText);
    sectionText(p,title,'.chart-legend',`━━ Quan sát lịch sử     ┄┄ Dự báo ${profile.name}     │ ${profile.horizon===24?'Phát hành: '+short(day)+' · 00:00':'Cập nhật sau từng giờ'}`);
  }
  text('#chart + .chart-note','Khoảng bất định: chưa cung cấp trong phiên bản hiện tại.');
  $('#chart').setAttribute('aria-label',trendText);$('#chart-dubao').setAttribute('aria-label',trendText);
  sectionText('tongquan','Nhịp điều động theo thứ và giờ','.sub',`Trung bình lượt/giờ · Toàn tập kiểm tra ${fmt(all.length,0)} giờ · Dữ liệu thật`);
  $('#heatmap').setAttribute('aria-label','Trung bình lượt điều động thực tế theo thứ và giờ trong tập kiểm tra');
  sectionText('tongquan','Các khung giờ nhu cầu cao','.sub',`${date(day)} · Dự báo ${profile.name} · ${mode}`);
  cellRows(section('tongquan','Các khung giờ nhu cầu cao').querySelector('.tbl'),['Khung giờ','Lượt dự báo','Đơn vị'],[...current].sort((a,b)=>b.prediction-a.prediction).slice(0,4).map(r=>[r.time.slice(11,16)+'–'+String(Number(r.time.slice(11,13))+1).padStart(2,'0')+':00',fmt(r.prediction),'lượt/giờ']),'peak-grid');
  values('#screen-tongquan .note-panel p',[ 'Lượt điều động không đồng nghĩa với số xe cần trực. Năng lực xe phụ thuộc thời gian bận và công việc kéo dài từ giờ trước.','Chưa đánh giá thiếu xe: bộ tính năng lực chưa được kết nối. Không lấy số lượt dự báo trừ số xe có thể bố trí.',`Đỉnh dự báo: ${fmt(peak.prediction)} lượt/giờ lúc ${peak.time.slice(11,16)}. Đây là tín hiệu nhu cầu, không phải số xe cần trực.`]);
  // Forecast configuration retains the original value-box and segmented styles.
  const config=section('dubao','Cấu hình dự báo');
  config.querySelector('.sub').textContent=`Chân trời đang xem: ${mode} · Độ chi tiết: theo giờ`;
  config.querySelector('.seg.sel').textContent=profile.horizon===24?'24 giờ · Đã chọn':'1 giờ · Đã chọn';
  const modelBox=config.querySelector('.value-box');modelBox.replaceChildren();const select=document.createElement('select');select.setAttribute('aria-label','Mô hình và chân trời dự báo');
  Object.entries(dataset.profiles).forEach(([k,p])=>{const option=document.createElement('option');option.value=k;option.textContent=`${p.name} · ${p.horizon} giờ`;option.selected=k===key;select.append(option);});
  modelBox.append(select);
  select.addEventListener('change',()=>{const url=new URL(location.href);url.searchParams.set('profile',select.value.replaceAll('_','-'));location.href=url.href;});
  config.querySelector('.field .sub').textContent='Các mô hình 24h được đối chiếu trên cùng 6.796 giờ kiểm tra.';
  config.querySelectorAll('.field')[1].querySelector('p').textContent=`Theo giờ · Ngày dự báo: ${date(day)}`;
  text('#screen-dubao .intro p',profile.description);
  text('#btn-forecast','Xem kết quả dự báo');
  values('#screen-dubao .mini-grid.c3 .m-value',profile.horizon===24?[date(day)+' · 00:00',date(previousDate.toISOString())+' · 23:00–24:00',date(day)+' · 00:00–24:00']:['Phát hành từng giờ','Thực tế đến hết giờ trước',date(day)+' · Đánh giá từng giờ']);
  config.querySelector(':scope > p:last-child').textContent='Huấn luyện đến hết 2024 · Chọn cấu hình trên validation 2025 · Kết quả đã lưu, không chạy lại mô hình trên web.';
  text('#screen-dubao .banner.green .b-title',`Đã tải ${current.length} khoảng dự báo có dữ liệu đối chiếu`);
  text('#screen-dubao .banner.green .b-text',`Tổng dự báo: ${fmt(forecastTotal)} lượt. ${current.length<24?'Ngày cuối chỉ có '+current.length+' giờ thực tế; không tự bù giờ thiếu.':'Dự báo thực nghiệm từ dữ liệu lịch sử, không phải dự báo thời gian thực.'}`);
  const forecastSection=section('dubao','Kết quả dự báo');forecastSection.querySelector('.sub').textContent=`${current.length} khoảng theo giờ · Đối chiếu lịch sử sau khi đã có thực tế`;
  cellRows(forecastSection.querySelector('.tbl'),['Thời gian','Lượt điều động thực tế','Lượt điều động dự báo','Sai lệch'],current.map(r=>[short(r.time)+' · '+r.time.slice(11,16),fmt(r.actual,0),fmt(r.prediction),fmt(r.prediction-r.actual)]),'fc-grid');
  sectionText('dubao','Trạng thái hiển thị','.sub','Thông tin về các trạng thái giao diện; dữ liệu hiện tại đã tải thành công.');
  values('#screen-dubao .status-cell .s-note',['Khi đang đọc bản kết quả đã lưu.','Chọn ngày thuộc phạm vi kiểm tra.','Kiểm tra kết nối và thử tải lại.',`${current.length} khoảng theo giờ đã tải.`]);
  text('#screen-dubao .status-cell.green .s-title','Đã có kết quả thật');
  // Preserve capacity/cost layouts; replace invented numbers by missing values.
  text('#screen-kehoach .banner .b-label','Chưa kết nối tính năng lực');
  sectionText('kehoach','Luồng tính năng lực','.sub',`Ngày được chọn: ${date(day)} · Thời gian theo dữ liệu nguồn`);
  text('#screen-kehoach .m-value.big',fmt(forecastTotal)+' lượt / ngày');
  text('#screen-kehoach .mini .m-note',`Prophet · ${mode} · Đơn vị theo giờ: lượt/giờ`);
  values('#screen-kehoach .value-box.big',['— phút','— %','— xe']);
  section('kehoach','Tham số và nguồn đầu vào').querySelectorAll('.m-note').forEach(n=>n.textContent='Chưa chốt đầu vào chung · Không dùng giá trị minh họa');
  $$('#screen-kehoach .plan-grid .tcell[data-label="Xe có thể bố trí"]').forEach(n=>n.textContent='Chưa có dữ liệu');
  sectionText('kehoach','Số xe cần trực ước tính và số xe có thể bố trí','.sub','Chờ phương pháp chung · Chưa có dữ liệu số xe để vẽ đường thực tế');
  sectionText('kehoach','Số xe cần trực ước tính và số xe có thể bố trí','.chart-legend','┄┄ Số xe cần trực ước tính     ━━ Số xe có thể bố trí · Chờ dữ liệu');
  sectionText('kehoach','Số xe cần trực ước tính và số xe có thể bố trí','.chart-note','Không hiển thị đường minh họa như kết quả thật. Chưa kết nối tính năng lực.');
  unavailableChart('chart-kehoach','Chưa có dữ liệu năng lực xe');
  sectionText('chiphi','Giả định chi phí','.sub',`Ngày phân tích: ${date(day)} · Chưa chốt đơn giá và nguồn lực`);
  $$('#screen-chiphi .value-box.big').forEach(n=>n.textContent='—');
  $$('#screen-chiphi .m-note').forEach(n=>n.textContent='Chờ đơn giá được nhóm thống nhất');
  // Evaluation uses all hours of this same horizon, never mixes H1 with H24.
  values('#screen-danhgia .k-value',[fmt(metrics.mae,4),fmt(metrics.mape,2)+'%','Prophet']);
  values('#screen-danhgia .k-note',[`Toàn bộ ${fmt(all.length,0)} giờ kiểm tra`,`MAPE trên ${fmt(metrics.percentageCount,0)} giờ có thực tế > 0`,'Chưa kết luận mô hình tốt nhất']);
  const setup=section('danhgia','Thiết lập đánh giá');
  cellRows(setup.querySelector('.tbl'),['Khoảng huấn luyện','Khoảng đánh giá','Số giờ','Chân trời dự báo'],[['Đến 31/12/2024',`${date(all[0].time)}–${date(all.at(-1).time)}`,fmt(all.length,0)+' giờ',mode]],'ev-grid');
  $$('#screen-danhgia .sub').forEach(n=>{if(/minh họa|168 giờ|chưa xác nhận|Chưa thay thế/i.test(n.textContent))n.textContent=`Dữ liệu lịch sử · ${mode} · ${fmt(all.length,0)} giờ kiểm tra`;});
  const comparison=section('danhgia','Bảng so sánh mô hình');
  cellRows(comparison.querySelector('.tbl'),['Mô hình','MAE (lượt/giờ)','MAPE (%)'],[['SARIMAX','Chờ kết quả chung','—'],['Prophet · '+mode,fmt(metrics.mae,4),fmt(metrics.mape,2)+'%'],['LSTM','Chờ kết quả chung','—'],['Cùng giờ tuần trước · Baseline','Chưa đóng gói','—']],'fr-grid');
  comparison.querySelectorAll('.sub')[1].textContent='Không xếp hạng chéo kết quả 1 giờ và 24 giờ; chưa đủ kết quả chung để chọn mô hình.';
  const hourTable=section('danhgia','Hiệu quả theo khung giờ');
  cellRows(hourTable.querySelector('.tbl'),['Khung giờ','Prophet','Cùng giờ tuần trước'],[0,6,12,18].map(h=>[String(h).padStart(2,'0')+'–'+String(h+6).padStart(2,'0'),fmt(score(all.filter(r=>Number(r.time.slice(11,13))>=h&&Number(r.time.slice(11,13))<h+6)).mae,4),'Chưa đóng gói']),'fr-grid');
  const method=section('danhgia','Phương pháp và phạm vi');
  const methodP=method.querySelectorAll('p:not(.sub)');
  methodP[0].textContent='Phạm vi: lượt điều động xe toàn thành phố San Francisco, sau khi lọc unit_type = MEDIC.';
  methodP[1].textContent=`Chế độ đang xem: ${mode}. ${profile.description}`;
  methodP[2].textContent='MAE: trung bình sai số tuyệt đối (lượt/giờ). MAPE: trung bình sai số phần trăm tuyệt đối; bỏ giờ thực tế bằng 0 khỏi MAPE, vẫn giữ trong MAE.';
  methodP[3].textContent=`Kết quả này dựa trên ${fmt(all.length,0)} giờ kiểm tra từ ${date(all[0].time)} đến ${date(all.at(-1).time)}. Không dùng dữ liệu năm 2026 để chọn cấu hình.`;
  const explanation=section('danhgia','Giải thích mô hình đang xem');
  explanation.querySelectorAll('p:not(.sub)')[1].textContent=`Chỉ chọn mô hình sau khi đối chiếu MAE và MAPE trên cùng dữ liệu, cùng chế độ ${mode}, cùng mốc huấn luyện và chính sách cập nhật.`;
  $$('#screen-danhgia .mini .m-value').forEach(n=>{if(/168|22\/09|23\/09/.test(n.textContent))n.textContent=`${fmt(all.length,0)} giờ`});
  sectionText('danhgia','Lượt điều động thực tế và dự báo','.sub',`${date(day)} · Đối chiếu sau khi có thực tế · ${mode}`);
  section('danhgia','Lượt điều động thực tế và dự báo').querySelectorAll('.sub')[1].textContent='Đơn vị: lượt/giờ · Xám đậm: thực tế · Nét đứt violet: dự báo';
  // Aggregated data cannot supply raw call IDs or busy times. Keep those cells empty.
  values('#screen-lichsu .k-value',['—',fmt(total,0)+' lượt','—','—']);
  values('#screen-lichsu .k-note',['Cần bản ghi gốc để đếm cuộc gọi duy nhất',`${range} · Tổng từ chuỗi thực tế`,'Chưa đóng gói kiểm tra bản ghi gốc','Chưa đóng gói mốc điều động và sẵn sàng']);
  sectionText('lichsu','Lịch sử lượt điều động xe','.sub',`${range} · Dữ liệu thật · Đơn vị: lượt/ngày · Tổng ${fmt(total,0)} lượt`);
  sectionText('lichsu','Lịch sử lượt điều động xe','.chart-note',`Trung bình: ${fmt(total/days)} lượt/ngày. Đây là lượt điều động, không phải số cuộc gọi duy nhất.`);
  const rawSection=section('lichsu','Bảng dữ liệu gốc · Lượt điều động');
  rawSection.querySelector('.sub').textContent='Chưa đóng gói bản ghi gốc trong dữ liệu web; không dựng mã cuộc gọi, mã xe hoặc thời gian bận.';
  cellRows($('#hist-table'),['Mã cuộc gọi','Mã sự cố','Mã xe','Thời điểm nhận','Điều động','Sẵn sàng','Thời gian bận','Cờ chất lượng'],[['—','—','—','—','—','—','—','Chưa có dữ liệu gốc']],'hist-grid');
  rawSection.querySelector('.link-accent').textContent='CSV hiện xuất chuỗi nhu cầu thực tế theo giờ trong phạm vi đang xem, không phải bản ghi gốc.';
  rawSection.querySelector('p.sub:last-child').textContent='Thời gian xe bận chỉ tính khi có đủ mốc điều động và sẵn sàng; không thay giá trị thiếu bằng 0.';
  $$('#screen-lichsu .toolbar .control').forEach((n,i)=>n.textContent=i===0?range:'Dữ liệu theo giờ');
  $('#hist-search').disabled=true;$('#hist-search').placeholder='Chưa đóng gói bản ghi gốc';
  const sourceSection=section('lichsu','Nguồn và phạm vi thời gian');
  cellRows(sourceSection.querySelector('.tbl'),['Thông tin','Trạng thái'],[['Nguồn dữ liệu','SF OpenData · nuek-vuh3'],['Giai đoạn kiểm tra',`${date(all[0].time)}–${date(all.at(-1).time)} · ${all.length} giờ`],['Phạm vi đang xem',range],['Ngày tải dữ liệu gốc','Chưa ghi nhận trong bản kết quả'],['Artifact',profile.source],['Commit nguồn',profile.revision||'CSV trên nhánh feat/demo'],['SHA-256',profile.sha256]],'src-grid');
  values('#screen-caidat .info-item .i-value',['SF OpenData','nuek-vuh3','San Francisco','unit_type = MEDIC','Kết quả đã lưu · '+all.length+' giờ',date(all[0].time)+'–'+date(all.at(-1).time),'Không phải dữ liệu thời gian thực','Theo dữ liệu nguồn; chưa chuyển đổi múi giờ']);
  values('#preview-table .trow:not(.head) .tcell',['—',date(day),'—','—',date(day),'—','—',date(day),'—']);
  text('#screen-caidat .card > .sub','Tùy chọn trình bày; lưu trên trình duyệt này.');
  text('#screen-caidat .actions-bar p','Các thay đổi chỉ áp dụng trên trình duyệt này.');
  // Assemble real series for the reference's own chart renderer and animation code.
  const maximum=Math.ceil(Math.max(1,...previous.map(r=>r.actual),...current.flatMap(r=>[r.actual,r.prediction]))/3)*3;
  const labels=[[before+' · 00:00',45,'start'],['12:00',300,'start'],[short(day)+' · 00:00',585,'start'],['12:00',840,'start'],['23:00',1110,'end']];
  const groups=Array.from({length:7},()=>Array.from({length:24},()=>[]));for(const r of context){const t=new Date(r.time+'Z');groups[(t.getUTCDay()+6)%7][t.getUTCHours()].push(r.actual);}
  const means=groups.map(d=>d.map(g=>g.length?g.reduce((a,b)=>a+b,0)/g.length:null)),heatMax=Math.max(1,...means.flat().filter(x=>x!==null));
  const daily=new Map();for(const r of context)daily.set(r.time.slice(0,10),(daily.get(r.time.slice(0,10))||0)+r.actual);
  const dailyValues=[...daily.values()],dailyMax=Math.ceil(Math.max(...dailyValues)/3)*3;
  const diffs=current.map(r=>r.prediction-r.actual);
  const grid=[maximum,maximum*2/3,maximum/3,0];
  const common={max:maximum,grid,xlabels:[['00:00',45],['06:00',320],['12:00',585],['18:00',850],['23:00',1110,'end']]};
  window.EMS={observed:previous.map(r=>r.actual),forecast:current.map(r=>r.prediction),peakHour:Number(peak.time.slice(11,13)),peakValue:peak.prediction,chartMax:maximum,timelineLabels:labels,overviewGrid:[[maximum,12],[maximum*2/3,76],[maximum/3,140],[0,204]],
    heatDays:means.map((d,i)=>[['Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy','Chủ nhật'][i],d.map(v=>[v===null?'Chưa có dữ liệu':Number(v.toFixed(1)),v===null?0:Math.min(3,Math.floor(v/heatMax*4))])]),
    charts:[{id:'chart-dubao',config:{...common,dividerX:586.3,xlabels:labels,series:[{data:previous.map(r=>r.actual),color:'#334155',day:0},{data:current.map(r=>r.prediction),color:'#754BFF',dash:true,day:1}]}},{id:'chart-danhgia',config:{...common,series:[{data:current.map(r=>r.actual),color:'#334155'},{data:current.map(r=>r.prediction),color:'#754BFF',dash:true}]}},{id:'chart-lichsu',config:{max:dailyMax,grid:[dailyMax,dailyMax*2/3,dailyMax/3,0],series:[{data:dailyValues,color:'#334155'}],xlabels:[...daily.keys()].filter((d,i)=>i===0||i%7===0||i===daily.size-1).map(d=>[short(d),45+[...daily.keys()].indexOf(d)/Math.max(1,daily.size-1)*1060])}}],diffs,diffScale:70/Math.max(1,...diffs.map(Math.abs)),
    download(){const url=URL.createObjectURL(new Blob([csv(context,[{key:'time',label:'Thời gian nguồn'},{key:'actual',label:'Lượt điều động xe thực tế'},{key:'prediction',label:profile.name+' '+profile.horizon+'h'}])],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`ems-nhu-cau-${month}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},saveSettings,restoreSettings,initialScreen:['tongquan','dubao','daily','kehoach','chiphi','danhgia','lichsu','caidat'].includes(initialScreen)?initialScreen:null};
  $('#chart-danhgia').setAttribute('aria-label',`Thực tế và dự báo ${profile.name} ngày ${date(day)}`);
  $('#chart-sailech').setAttribute('aria-label',`Sai lệch dự báo trừ thực tế theo giờ ngày ${date(day)}`);
  $('#chart-lichsu').setAttribute('aria-label',`Lượt điều động xe thực tế theo ngày ${range}`);
  enhanceOperations(dataset,key,day);restoreSettings();await import('./template-runtime.mjs');installReferenceMotion();installZenlessShell();installLiveForecast();document.body.classList.add('data-ready');
}
const status=document.createElement('p');status.className='data-loading';status.setAttribute('role','status');status.textContent='Đang tải dữ liệu thật…';document.body.append(status);
start().catch(error=>{status.textContent=error.message;});
