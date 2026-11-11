// Presentation only: the existing screen buttons and data handlers remain the source of truth.
export function installZenlessShell(){
  const $=s=>document.querySelector(s);
  const nav=$('.nav'), buttons=[...nav.querySelectorAll('[data-screen]')];
  const reduced=()=>document.body.classList.contains('reduce-motion')||window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  $('.brand .mark').innerHTML='<span>EMS</span>';
  const more=document.createElement('details');more.className='zzz-more';
  more.innerHTML='<summary>Thêm<span class="zzz-more-arrow" aria-hidden="true"></span></summary><div class="zzz-dropdown"></div>';
  buttons.slice(6).forEach(button=>more.lastElementChild.append(button));nav.append(more);
  const launch=document.createElement('button');launch.type='button';launch.className='zzz-launch';launch.textContent='Xem dự báo';
  launch.addEventListener('click',()=>nav.querySelector('[data-screen="daily"]').click());$('.sidebar').append(launch);
  const rail=document.createElement('nav');rail.className='zzz-rail';rail.setAttribute('aria-label','Chuyển màn hình nhanh');
  buttons.forEach((button,i)=>{
    const item=document.createElement('button');item.type='button';item.textContent=String(i+1).padStart(2,'0');item.title=button.textContent.trim();item.setAttribute('aria-label',item.title);
    item.addEventListener('click',()=>button.click());rail.append(item);
    button.addEventListener('click',()=>{more.open=false;sync();});
  });document.body.append(rail);
  function sync(){
    const current=buttons.findIndex(b=>b.classList.contains('active'));
    [...rail.children].forEach((b,i)=>{b.classList.toggle('active',i===current);if(i===current)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    more.classList.toggle('selected',current>=6);
    const opening=document.querySelector('.zzz-hero');if(opening)opening.hidden=current!==0;
  }sync();
  window.addEventListener('popstate',sync);
  document.addEventListener('click',e=>{if(!more.contains(e.target))more.open=false;});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){more.open=false;more.querySelector('summary').focus();}});
  const hero=document.createElement('section');hero.className='zzz-hero';hero.setAttribute('aria-label','EMSForecast — Trung tâm dự báo');
  hero.innerHTML=`<div class="zzz-hero-copy"><p class="zzz-location">San Francisco / EMSForecast</p><h2>DỰ BÁO<br>NHU CẦU.<br><span>SẴN SÀNG<br>ĐIỀU ĐỘNG.</span></h2><p class="zzz-description">Từ nhịp điều động của thành phố<br>đến kế hoạch xe cho từng ca trực.</p><button type="button" class="zzz-hero-cta">KHÁM PHÁ DỰ BÁO <span aria-hidden="true">↗</span></button><p class="zzz-disclaimer">Nghiên cứu trên dữ liệu lịch sử.<br>Ước tính hỗ trợ lập kế hoạch xe cứu thương.</p></div>
  <div class="zzz-art" aria-hidden="true"><div class="zzz-orbit"></div><div class="zzz-art-word">EMS</div>
  <svg class="zzz-city" viewBox="0 0 720 580" fill="none"><defs><pattern id="city-grid" width="44" height="44" patternUnits="userSpaceOnUse"><path d="M44 0H0V44" stroke="#b1b1ab" stroke-width="1"/></pattern></defs><path d="M0 0H720V580H0Z" fill="url(#city-grid)"/>
  <g stroke="#a8a8a1" stroke-width="2"><path d="M0 130H720M0 350H720M180 0V580M480 0V580" stroke-width="16"/><path d="M70 40h70v55H70zM230 38h90v60h-90zM350 35h80v65h-80zM520 40h145v60H520zM40 190h100v110H40zM230 180h95v110h-95zM355 180h70v110h-70zM535 180h130v120H535zM40 410h100v130H40zM235 410h190v130H235zM535 410h130v130H535z" fill="#c8c8c2"/></g>
  <path class="zzz-route" d="M60 350H180V130H480V350H650" stroke="#151515" stroke-width="6" stroke-dasharray="14 9"/>
  <g transform="translate(185 212) rotate(-9 180 100)"><path d="M15 50L50 14H240L290 65H344L370 113V195H8V92Z" fill="#181818" stroke="#181818" stroke-width="14" stroke-linejoin="round"/><path d="M19 52L52 19H235L282 70H339L362 116V167H18Z" fill="#f4f4ed"/><path d="M250 79H289L329 87L346 118H251Z" fill="#505754" stroke="#181818" stroke-width="5"/><path d="M20 123H359V147H20Z" fill="#ddfc42"/><path d="M232 27V162" stroke="#181818" stroke-width="5"/><path d="M78 49H111V71H133V104H111V126H78V104H56V71H78Z" fill="#181818"/><path d="M161 42H207V100H161Z" fill="#cad0ca" stroke="#181818" stroke-width="4"/><path d="M267 150H285" stroke="#181818" stroke-width="5"/><rect x="173" y="3" width="52" height="15" rx="4" fill="#ddfc42" stroke="#181818" stroke-width="5"/><circle cx="85" cy="179" r="32" fill="#181818" stroke="#eee" stroke-width="5"/><circle cx="85" cy="179" r="13" fill="#ddfc42"/><circle cx="302" cy="179" r="32" fill="#181818" stroke="#eee" stroke-width="5"/><circle cx="302" cy="179" r="13" fill="#ddfc42"/></g>
  <circle cx="480" cy="130" r="17" fill="#ddfc42" stroke="#151515" stroke-width="6"/><circle cx="650" cy="350" r="17" fill="#ddfc42" stroke="#151515" stroke-width="6"/></svg>
  <div class="zzz-art-tag">SẴN SÀNG CHO<br><strong>CA TRỰC TIẾP THEO</strong><span>↗</span></div><div class="zzz-art-caption">Nhu cầu theo giờ / Kế hoạch theo ca</div></div>
  <div class="zzz-hero-bottom"><span>EMSFORECAST / OPERATIONS</span><button type="button" class="zzz-explore">Xem tổng quan <span aria-hidden="true">↓</span></button></div>`;
  $('.topbar').after(hero);sync();
  hero.querySelector('.zzz-hero-cta').addEventListener('click',()=>nav.querySelector('[data-screen="daily"]').click());
  hero.querySelector('.zzz-explore').addEventListener('click',()=>$('#screen-tongquan .intro').scrollIntoView({behavior:reduced()?'auto':'smooth',block:'start'}));
  buttons.forEach((button,i)=>{
    const page=$('#screen-'+button.dataset.screen);
    page.dataset.chapter=String(i+1).padStart(2,'0');
    page.querySelector('.intro')?.setAttribute('data-chapter',page.dataset.chapter);
  });
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button||button.disabled||reduced())return;
    button.classList.remove('zzz-hit');void button.offsetWidth;button.classList.add('zzz-hit');
    setTimeout(()=>button.classList.remove('zzz-hit'),360);
  });
}
