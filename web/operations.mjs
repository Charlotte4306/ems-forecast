import {score} from './dashboard.mjs';
import {screenFromLocation} from './routes.mjs';

export function dailyPlan(operations, profile, day, policy='mean', shift='shift8', ratio=3) {
  if (!operations || ![2,3,5,10,20].includes(ratio)) return null;
  const rows=operations.rows.filter(r=>r.time.slice(0,10)===day);
  const selected=rows.map(r=>({...r,plan:r.plans[profile]?.[policy]?.[shift]??null}));
  const complete=selected.filter(r=>r.plan!==null);
  let shortage=0,excess=0;
  for(const r of complete){shortage+=Math.max(0,r.need-r.plan);excess+=Math.max(0,r.plan-r.need);}
  return {rows:selected,hours:complete.length,excluded:rows.length-complete.length,shortage,excess,cost:excess+ratio*shortage,peak:complete.length?Math.max(...complete.map(r=>r.plan)):null};
}

const $=s=>document.querySelector(s);
const fmt=(n,d=1)=>n===null||n===undefined?'—':n.toLocaleString('vi-VN',{maximumFractionDigits:d});
const table=(headers,rows)=>`<div class="ops-table-wrap"><table class="ops-table"><thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const detail=(title,body)=>{const node=document.createElement('details');node.className='card ops-details';const summary=document.createElement('summary');summary.textContent=title;node.append(summary,body);return node;};

export function enhanceOperations(dataset,key,day) {
  const profile=dataset.profiles[key],query=new URLSearchParams(location.search);
  const policy=['mean','p90'].includes(query.get('policy'))?query.get('policy'):'mean';
  const shift=['shift8','shift12'].includes(query.get('shift'))?query.get('shift'):'shift8';
  const ratio=[2,3,5,10,20].includes(Number(query.get('ratio')))?Number(query.get('ratio')):3;
  const plan=profile.horizon===24?dailyPlan(dataset.operations,key,day,policy,shift,ratio):null;
  const current=profile.rows.filter(r=>r.time.startsWith(day));
  const peak=current.reduce((a,b)=>b.prediction>a.prediction?b:a);
  const modelKeys=Object.keys(dataset.profiles).filter(k=>dataset.profiles[k].horizon===24);
  const navigate=target=>document.querySelector(`.nav button[data-screen="${target}"]`)?.click();
  const flow=document.createElement('nav');flow.className='ops-flow';flow.setAttribute('aria-label','Các bước sử dụng');
  const icons=['<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>','<path d="M3 19h18M4 15l5-5 4 3 7-9M15 4h5v5"/>','<path d="M3 17V8h13l5 6v3H3M16 8v6h5M7 8v6M4 11h6"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>','<path d="M4 4h16v16H4zM8 8h8M8 12h2M14 12h2M8 16h2M14 16h2"/>'];
  [['lichsu','Dữ liệu'],['dubao','Dự báo'],['kehoach','Kế hoạch xe'],['chiphi','Chi phí']].forEach(([target,label],i)=>{
    const button=document.createElement('button');button.type='button';button.dataset.destination=target;button.innerHTML=`<svg aria-hidden="true" viewBox="0 0 24 24">${icons[i]}</svg><span><small>Bước ${i+1}</small>${label}</span>`;button.addEventListener('click',()=>navigate(target));flow.append(button);
  });
  function markStep(target){flow.querySelectorAll('button').forEach(button=>{if(button.dataset.destination===target)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');});}
  markStep(screenFromLocation(location));document.querySelectorAll('.nav button[data-screen]').forEach(button=>button.addEventListener('click',()=>markStep(button.dataset.screen)));
  window.addEventListener('popstate',()=>markStep(screenFromLocation(location)));
  $('#screens').before(flow);
  const controls=document.createElement('div');controls.className='ops-controls';
  function choose(label,param,options,value){
    const host=document.createElement('label');host.append(document.createTextNode(label));const select=document.createElement('select');select.setAttribute('aria-label',label);
    options.forEach(([v,t])=>{const option=document.createElement('option');option.value=v;option.textContent=t;option.selected=String(v)===String(value);select.append(option);});
    select.addEventListener('change',()=>{const url=new URL(location.href);url.searchParams.set(param,param==='profile'?select.value.replaceAll('_','-'):select.value);location.href=url.href;});host.append(select);controls.append(host);
  }
  choose('Mô hình','profile',modelKeys.map(k=>[k,dataset.profiles[k].name+' · 24h']),key);
  choose('Phương án','policy',[['mean','Trung bình'],['p90','P90 · Thận trọng']],policy);
  choose('Kiểu ca','shift',[['shift8','3 ca × 8 giờ'],['shift12','2 ca × 12 giờ']],shift);
  choose('Chi phí thiếu / thừa','ratio',[2,3,5,10,20].map(r=>[r,r+' : 1']),ratio);
  flow.after(controls);
  if(profile.horizon!==24) {controls.querySelector('select').selectedIndex=-1;const option=document.createElement('option');option.value=key;option.disabled=true;option.textContent=profile.name+' · 1h (bổ sung)';option.selected=true;controls.querySelector('select').append(option);}

  const overview=$('#screen-tongquan'),kpis=overview.querySelector('.kpis');
  kpis.classList.add('ops-summary');
  kpis.innerHTML=[['Lượt điều động dự báo',fmt(current.reduce((s,r)=>s+r.prediction,0)),`${current.length} giờ có dữ liệu đối chiếu`],['Giờ nhu cầu cao nhất',peak.time.slice(11,16),fmt(peak.prediction)+' lượt/giờ'],['Xe bố trí cao nhất',fmt(plan?.peak,0),plan?.hours?`${policy==='p90'?'P90':'Trung bình'} · Mức bận 80%`:'Chưa có ca hoàn chỉnh']].map(([label,value,note])=>`<div class="kpi"><div class="k-label">${label}</div><div class="k-value num">${value}</div><div class="k-note">${note}</div></div>`).join('');
  const cards=[...overview.querySelectorAll(':scope > section.card')];
  const trend=cards.find(n=>n.querySelector('#chart'));
  const heat=cards.find(n=>n.querySelector('#heatmap'));
  const definitions=cards.find(n=>n.textContent.includes('Ba đại lượng'));
  const peakWrap=overview.querySelector('.peak-wrap');
  const note=peakWrap.querySelector('.note-panel');
  const focus=document.createElement('div');focus.className='ops-focus';trend.before(focus);focus.append(trend,note);
  note.innerHTML=`<h2>Điểm cần chú ý</h2><p class="ops-peak-time">${peak.time.slice(11,16)}</p><p>Giờ nhu cầu cao nhất trong ngày được chọn: <strong>${fmt(peak.prediction)} lượt/giờ</strong>.</p><p>${plan?.hours?`Phương án đang xem bố trí tối đa <strong>${fmt(plan.peak,0)} xe</strong> trong một ca.`:'Ngày hoặc chế độ này chưa có kế hoạch ca hoàn chỉnh.'}</p><button type="button" class="btn-primary" id="ops-view-plan">Xem kế hoạch xe</button><p class="sub">Ước tính hỗ trợ lập kế hoạch, không phải lịch trực thực tế.</p>`;
  $('#ops-view-plan').addEventListener('click',()=>navigate('kehoach'));
  const secondary=document.createElement('div');secondary.className='ops-secondary';focus.after(secondary);
  heat.classList.add('ops-heat-card');heat.querySelector('h2').textContent='Nhịp nhu cầu trong tuần';
  heat.querySelector('.sub').textContent='Trung bình lượt/giờ theo thứ và giờ trong giai đoạn lịch sử tham chiếu.';
  const miniature=document.createElement('div');miniature.className='ops-mini-heat';miniature.setAttribute('role','img');miniature.setAttribute('aria-label','Nhịp nhu cầu theo thứ và giờ; mở rộng để xem nhãn và giá trị');
  for(const [weekday,cells] of window.EMS.heatDays)for(const [hour,cell] of cells.entries()){const dot=document.createElement('span');dot.style.background=`var(--heat-${cell[1]})`;dot.title=`${weekday} ${hour}:00 · ${cell[0]} lượt/giờ`;miniature.append(dot);}
  heat.querySelector('.sub').after(miniature);
  const heatDetails=detail('Mở rộng nhịp nhu cầu',heat.querySelector('.heatmap'));heat.append(heatDetails);
  secondary.append(heat,peakWrap.querySelector('section'));peakWrap.remove();
  const readBody=document.createElement('div');readBody.append(definitions);const read=detail('Cách đọc kết quả',readBody);secondary.after(read);definitions.classList.remove('card');
  const hint=document.createElement('p');hint.textContent='Lượt điều động → khối lượng xe bận → số xe bố trí → chi phí thiếu/thừa. P90 là phương án thận trọng, không bảo đảm luôn đủ xe. Lịch được lập tại 00:00, chưa mô phỏng thông báo trước ca.';readBody.prepend(hint);
  overview.querySelector('.intro p').textContent='Chọn ngày và mô hình, xem nhu cầu rồi đối chiếu kế hoạch xe.';

  const label=policy==='p90'?'P90':'Trung bình',length=shift==='shift8'?8:12;
  const groups=[];
  if(plan)for(let h=0;h<24;h+=length){const rows=plan.rows.filter(r=>{const t=Number(r.time.slice(11,13));return t>=h&&t<h+length;});const valid=rows.length===length&&rows.every(r=>r.plan!==null);groups.push([`${String(h).padStart(2,'0')}:00–${String(h+length).padStart(2,'0')}:00`,valid?fmt(rows[0].plan,0)+' xe':'Chưa đủ ca',valid?fmt(Math.max(...rows.map(r=>r.need)),0)+' xe':'—',valid?fmt(rows.reduce((s,r)=>s+Math.max(0,r.need-r.plan),0)):'—']);}
  $('#screen-kehoach').innerHTML=`<div class="intro"><h1>Kế hoạch xe</h1><p>${day} · ${profile.name} · ${label} · Mức bận tối đa 80%</p></div><section class="card"><h2>Bố trí theo ca</h2><p class="sub">${shift==='shift8'?'00–08, 08–16, 16–24':'00–12, 12–24'} · Phát hành dự báo lúc 00:00</p>${plan?table(['Ca','Xe bố trí theo phương án','Nhu cầu xe ước tính cao nhất¹','Xe-giờ thiếu¹'],groups):'<p>Chưa có dữ liệu năng lực tương ứng. Chọn mô hình 24h để xem kế hoạch.</p>'}<p class="sub">¹ Hậu kiểm từ nhu cầu thực tế và thời gian bận ước lượng; không phải số xe trực quan sát được.</p></section><section class="card"><h2>Đối chiếu theo giờ</h2>${plan?table(['Giờ','Xe bố trí','Nhu cầu xe ước tính¹','Chênh lệch'],plan.rows.map(r=>[r.time.slice(11,16),fmt(r.plan,0),fmt(r.need,0),r.plan===null?'Chưa đủ ca':fmt(r.plan-r.need,0)])):'<p>Không có dữ liệu phù hợp.</p>'}</section><details class="card ops-details"><summary>Cách tính năng lực và giới hạn</summary><p>Dùng kernel thời gian xe bận từ dữ liệu 2025 để tính khối lượng công việc kéo dài qua các giờ. Nhu cầu xe = làm tròn lên (khối lượng xe bận / 0,8). Mỗi ca bố trí theo mức cao nhất trong ca. Đây là kịch bản, chưa xét vị trí xe và thời gian di chuyển.</p><p>Phần theo giờ: 6.796 giờ. Đánh giá ca: 6.792 giờ; loại 4 giờ cuối chưa đủ ca. Ngày đang xem: ${plan?.hours??0} giờ chấm, ${plan?.excluded??0} giờ loại.</p></details>`;
  $('#screen-chiphi').innerHTML=`<div class="intro"><h1>Chi phí kịch bản</h1><p>Hậu kiểm ngày ${day} · ${profile.name} · ${label}</p></div><section class="card"><h2>Chi phí khi dự báo sai</h2><p class="sub">Điểm chi phí kịch bản; không phải chi phí tiền tệ thực tế.</p><div class="ops-cost-value num">${plan?.hours?fmt(plan.cost):'—'} <small>điểm</small></div>${table(['Xe-giờ thừa','Xe-giờ thiếu','Tỷ lệ thiếu / thừa','Số giờ chấm'],[[plan?.hours?fmt(plan.excess):'—',plan?.hours?fmt(plan.shortage):'—',ratio+' : 1',plan?.hours??0]])}<p>Điểm chi phí = xe-giờ thừa + ${ratio} × xe-giờ thiếu.</p><p class="sub">${plan?.hours?'Đối chiếu với nhu cầu xe ước tính từ thực tế.':'Chưa có ca hoàn chỉnh để tính chi phí.'} Không dùng chi phí test để chọn phân vị tối ưu.</p></section><section class="card"><h2>So sánh cùng kịch bản trên toàn tập kiểm tra</h2><p class="sub">6.792 giờ thuộc các ca hoàn chỉnh · ${label} · Cùng kiểu ca và tỷ lệ chi phí</p>${dataset.operations?table(['Mô hình','Xe-giờ thiếu','Xe-giờ thừa','Điểm chi phí'],dataset.operations.reports.evaluation_shifts.filter(r=>r['Kiểu ca'].startsWith(shift==='shift8'?'3 ca':'2 ca')&&r['Kế hoạch theo']===label&&Number(r['ρ_max'])===0.8&&!r['Nguồn dự báo'].startsWith('Profile')).map(r=>[r['Nguồn dự báo'],fmt(Number(r['Xe-giờ thiếu'])),fmt(Number(r['Xe-giờ thừa'])),fmt(Number(r['Chi phí (thiếu = '+ratio+'× thừa)']))])):'<p>Chưa có bảng đánh giá.</p>'}<p class="sub">Chênh lệch chi phí chỉ mô tả tập kiểm tra và kịch bản này, không phải khuyến nghị đã kiểm chứng cho tương lai.</p></section>`;

  const comparison=[...document.querySelectorAll('#screen-danhgia section')].find(n=>n.querySelector('h2')?.textContent==='Bảng so sánh mô hình');
  const comparable=Object.values(dataset.profiles).filter(p=>p.horizon===profile.horizon);
  comparison.querySelector('.tbl').outerHTML=table(['Mô hình','MAE (lượt/giờ)','MAPE (%)'],comparable.map(p=>{const m=score(p.rows);return [p.name,fmt(m.mae,4),fmt(m.mape,2)+'%'];}));
  comparison.querySelectorAll('.sub')[1].textContent=`Chỉ so sánh cùng chân trời ${profile.horizon} giờ trên cùng tập kiểm tra. MAE và MAPE có thể ưu tiên các mô hình khác nhau.`;
  const hourTable=[...document.querySelectorAll('#screen-danhgia section')].find(n=>n.querySelector('h2')?.textContent==='Hiệu quả theo khung giờ');
  hourTable.querySelector('.tbl').outerHTML=table(['Khung giờ','MAE · '+profile.name],[0,6,12,18].map(h=>[`${h}–${h+6}`,fmt(score(profile.rows.filter(r=>{const t=Number(r.time.slice(11,13));return t>=h&&t<h+6;})).mae,4)]));
  document.querySelectorAll('#screen-danhgia .k-value')[2].textContent=profile.name;
  const explanation=[...document.querySelectorAll('#screen-danhgia section')].find(n=>n.querySelector('h2')?.textContent==='Giải thích mô hình đang xem');
  explanation.querySelectorAll('p:not(.sub)')[0].textContent=profile.name==='Prophet'?'Prophet kết hợp xu hướng, chu kỳ và các đặc trưng lịch sử.':profile.name==='SARIMAX'?'SARIMAX kết hợp Fourier, biến lịch và sai số ARMA; tham số không refit bằng validation.':'LSTM dùng cửa sổ 24 giờ, 34 đặc trưng và checkpoint huấn luyện offline; xuất trực tiếp 24 giá trị cho cả ngày.';
  document.querySelectorAll('#screen-dubao .status-grid').forEach(n=>n.closest('section').hidden=true);
  const help=document.createElement('p');help.className='sub';help.textContent='Dữ liệu lịch sử đã lưu · Chưa có luồng dữ liệu trực tiếp · Các tham số chi phí là kịch bản.';controls.after(help);
}
