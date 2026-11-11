
(function(){
  "use strict";
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches || document.body.classList.contains('reduce-motion');

  /* ---------- Parallax nhẹ cho lớp nền pastel khi di chuột ---------- */
  if(!reduced){
    var blobs = document.querySelectorAll('.blob');
    var tx = 0, ty = 0, cx = 0, cy = 0;
    document.addEventListener('mousemove', function(e){
      tx = (e.clientX / window.innerWidth - .5);
      ty = (e.clientY / window.innerHeight - .5);
    });
    (function loop(){
      if(document.body.classList.contains('reduce-motion')){ requestAnimationFrame(loop); return; }
      cx += (tx - cx) * .04; cy += (ty - cy) * .04;
      blobs.forEach(function(b){
        var d = parseFloat(b.getAttribute('data-depth') || 10);
        b.style.translate = (cx * d) + 'px ' + (cy * d) + 'px';
      });
      requestAnimationFrame(loop);
    })();
  }

  /* ---------- Biểu đồ: đúng hình học Figma — khung 1120×250, lưới 30/20/10/0 ở y 12/76/140/204,
       đường quan sát 28/09 (x 45→564) và dự báo 29/09 (x 586→1105), vạch chia dự báo ở x 586 ---------- */
  var observed = window.EMS.observed;
  var forecast = window.EMS.forecast;
  var svg = document.getElementById('chart');
  var NS = 'http://www.w3.org/2000/svg';
  function el(tag, attrs, parent){
    var n = document.createElementNS(NS, tag);
    for(var k in attrs) n.setAttribute(k, attrs[k]);
    if(parent) parent.appendChild(n);
    return n;
  }
  function X(day, h){ return 45 + day * 541.277 + h * 22.5532; }
  function Y(v){ return 204 - 192 * v / window.EMS.chartMax; }
  function linePath(data, day){
    return data.map(function(d, i){ return (i === 0 ? 'M' : 'L') + X(day, i).toFixed(1) + ' ' + Y(d).toFixed(1); }).join(' ');
  }
  // Lưới ngang + nhãn trục Y (12px)
  window.EMS.overviewGrid.forEach(function(g){
    el('line', {x1:45, x2:1105, y1:g[1], y2:g[1], stroke:'#E7E3EF', 'stroke-width':1}, svg);
    var t = el('text', {x:32, y:g[1] + 4, 'text-anchor':'end', 'font-size':12, fill:'#666575'}, svg);
    t.textContent = g[0];
  });
  // Vạch bắt đầu dự báo
  el('line', {x1:586.3, x2:586.3, y1:0, y2:205, stroke:'#E7E3EF', 'stroke-width':1}, svg);
  // Nhãn trục X (12px)
  window.EMS.timelineLabels.forEach(function(l){
    var t = el('text', {x:l[1], y:242, 'text-anchor':l[2], 'font-size':12, fill:'#666575'}, svg);
    t.textContent = l[0];
  });
  // Đường quan sát — liền, #334155
  el('path', {d:linePath(observed, 0), fill:'none', stroke:'#334155', 'stroke-width':2.4,
    'stroke-linejoin':'round', 'stroke-linecap':'round', pathLength:'1',
    'class': reduced ? '' : 'draw-line'}, svg);
  // Đường dự báo — đứt nét, #754BFF
  var fc = el('path', {d:linePath(forecast, 1), fill:'none', stroke:'#754BFF', 'stroke-width':2.4,
    'stroke-linejoin':'round', 'stroke-linecap':'round'}, svg);
  fc.style.strokeDasharray = '7 5';
  // Điểm đỉnh dự báo 18:00 — nhấp nháy như bản trước (hiệu ứng, không đổi số liệu)
  var peakX = X(1, window.EMS.peakHour), peakY = Y(window.EMS.peakValue);
  if(!reduced){
    var halo = el('circle', {cx:peakX, cy:peakY, r:5, fill:'none', stroke:'#754BFF', 'stroke-width':2}, svg);
    var animR = document.createElementNS(NS, 'animate');
    animR.setAttribute('attributeName', 'r'); animR.setAttribute('values', '5;17');
    animR.setAttribute('dur', '1.9s'); animR.setAttribute('repeatCount', 'indefinite');
    halo.appendChild(animR);
    var animO = document.createElementNS(NS, 'animate');
    animO.setAttribute('attributeName', 'opacity'); animO.setAttribute('values', '.75;0');
    animO.setAttribute('dur', '1.9s'); animO.setAttribute('repeatCount', 'indefinite');
    halo.appendChild(animO);
  }
  el('circle', {cx:peakX, cy:peakY, r:4.5, fill:'#754BFF', stroke:'#fff', 'stroke-width':1.6}, svg);

  /* ---------- Số KPI đếm lên khi tải trang (kết thúc đúng giá trị gốc) ---------- */
  if(!reduced){
    document.querySelectorAll('.k-value[data-count]').forEach(function(node, idx){
      var target = parseFloat(node.getAttribute('data-count'));
      var suffix = node.getAttribute('data-suffix') || '';
      var dur = 1300, start = null;
      function fmt(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
      function step(ts){
        if(!start) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        node.textContent = Number(target * eased).toLocaleString('vi-VN', {maximumFractionDigits: Number(node.dataset.decimals || 0)}) + suffix;
        if(p < 1) requestAnimationFrame(step);
      }
      setTimeout(function(){ requestAnimationFrame(step); }, 150 + idx * 120);
    });
  }

  /* ---------- Heatmap: đúng 168 ô của Figma — [giá trị lượt/giờ, mức màu 0–3] từng thứ ---------- */
  var heatDays = window.EMS.heatDays;
  var hm = document.getElementById('heatmap');
  function fmt(v){ return String(v).replace('.', ','); }
  var corner = document.createElement('div');
  corner.className = 'hm-corner'; corner.textContent = 'Thứ / giờ'; hm.appendChild(corner);
  for(var hh = 0; hh < 24; hh++){
    var hd = document.createElement('div');
    hd.className = 'hm-h'; hd.textContent = (hh < 10 ? '0' : '') + hh;
    hm.appendChild(hd);
  }
  heatDays.forEach(function(day, di){
    var dl = document.createElement('div');
    dl.className = 'hm-d'; dl.textContent = day[0]; hm.appendChild(dl);
    day[1].forEach(function(cell, hr){
      var c = document.createElement('div');
      c.className = 'hm-cell';
      c.style.background = 'var(--heat-' + cell[1] + ')';
      if(!reduced) c.style.animationDelay = ((di * 24 + hr) * 4) + 'ms';
      c.setAttribute('tabindex', '0');
      var label = day[0] + ' · ' + (hr < 10 ? '0' : '') + hr + ':00 · ' + fmt(cell[0]) + ' lượt/giờ · dữ liệu lịch sử';
      c.setAttribute('aria-label', label);
      c.setAttribute('title', label);
      hm.appendChild(c);
    });
  });

  /* ---------- Chuyển màn bằng sidebar ---------- */
  var titles = {tongquan:'Tổng quan', dubao:'Dự báo nhu cầu', kehoach:'Kế hoạch xe', chiphi:'Chi phí kịch bản', danhgia:'Đánh giá mô hình', lichsu:'Dữ liệu lịch sử', caidat:'Cài đặt'};
  var crumb = document.getElementById('crumb');
  var topFilters = document.getElementById('topbar-filters');
  function showScreen(key){
    document.querySelectorAll('.nav button[data-screen]').forEach(function(b){
      var on = b.getAttribute('data-screen') === key;
      b.classList.toggle('active', on);
      if(on){ b.setAttribute('aria-current','page'); if(!b.querySelector('.ind')){ var i=document.createElement('span'); i.className='ind'; i.setAttribute('aria-hidden','true'); b.appendChild(i); } }
      else { b.removeAttribute('aria-current'); var ind=b.querySelector('.ind'); if(ind) ind.remove(); }
    });
    document.querySelectorAll('#screens .page').forEach(function(p){ p.classList.toggle('active', p.id === 'screen-' + key); });
    if(crumb) crumb.textContent = titles[key] || '';
    if(topFilters) topFilters.style.display = (key === 'caidat') ? 'none' : '';
    window.scrollTo(0, 0);
  }
  document.querySelectorAll('.nav button[data-screen]').forEach(function(b){
    b.addEventListener('click', function(){ showScreen(b.getAttribute('data-screen')); history.replaceState(null, '', '#' + b.getAttribute('data-screen')); });
  });
  if(window.EMS.initialScreen) showScreen(window.EMS.initialScreen);
  var gotoHist = document.getElementById('btn-goto-history');
  if(gotoHist) gotoHist.addEventListener('click', function(){ showScreen('lichsu'); });

  /* ---------- Vẽ biểu đồ dùng chung (khung 1120×250 như Figma) ---------- */
  function drawChart(svgId, cfg){
    var s = document.getElementById(svgId); if(!s) return;
    var W = cfg.w || 1120, base = 204, top = 12;
    cfg.grid.forEach(function(g){
      var y = base - (base - top) * (g / cfg.max);
      el('line', {x1:45, x2:W - 15, y1:y, y2:y, stroke:'#E7E3EF', 'stroke-width':1}, s);
      var t = el('text', {x:32, y:y + 4, 'text-anchor':'end', 'font-size':12, fill:'#666575'}, s);
      t.textContent = g;
    });
    function px(i, n){ return 45 + i * ((W - 60) / Math.max(1, n - 1)); }
    function py(v){ return base - (base - top) * (v / cfg.max); }
    cfg.series.forEach(function(ser){
      var d = ser.data.map(function(v, i){ return (i === 0 ? 'M' : 'L') + (ser.day === undefined ? px(i, ser.data.length) : X(ser.day, i)).toFixed(1) + ' ' + py(v).toFixed(1); }).join(' ');
      var p = el('path', {d:d, fill:'none', stroke:ser.color, 'stroke-width':2.4, 'stroke-linejoin':'round', 'stroke-linecap':'round'}, s);
      if(ser.dash) p.style.strokeDasharray = '7 5';
      else if(!reduced){ p.setAttribute('pathLength','1'); p.setAttribute('class','draw-line'); }
    });
    if(cfg.flatY !== undefined){
      el('line', {x1:45, x2:W - 15, y1:py(cfg.flatY), y2:py(cfg.flatY), stroke:'#334155', 'stroke-width':2.4}, s);
    }
    if(cfg.dividerX !== undefined){
      el('line', {x1:cfg.dividerX, x2:cfg.dividerX, y1:0, y2:205, stroke:'#E7E3EF', 'stroke-width':1}, s);
    }
    cfg.xlabels.forEach(function(l){
      var t = el('text', {x:l[1], y:242, 'text-anchor':l[2] || 'start', 'font-size':12, fill:'#666575'}, s);
      t.textContent = l[0];
    });
  }
  window.EMS.charts.forEach(function(item){ drawChart(item.id, item.config); });
  // Sai lệch theo giờ (cột, khung 560×190): dương = violet, âm = cam nâu như Figma
  (function(){
    var s = document.getElementById('chart-sailech'); if(!s) return;
    var diffs = window.EMS.diffs;
    var zeroY = 78, scale = window.EMS.diffScale, x0 = 30, step = 21.5, bw = 11;
    el('line', {x1:8, x2:552, y1:zeroY, y2:zeroY, stroke:'#E7E3EF', 'stroke-width':1}, s);
    diffs.forEach(function(v, i){
      var h = Math.abs(v) * scale;
      el('rect', {x:x0 + i * step, y: v >= 0 ? zeroY - h : zeroY, width:bw, height:Math.max(h, 2), rx:2,
        fill: v >= 0 ? '#754BFF' : '#C26A06'}, s);
    });
    [['00:00',30],['06:00',159],['12:00',288],['18:00',417]].forEach(function(l){
      var t = el('text', {x:l[1], y:172, 'font-size':12, fill:'#666575'}, s);
      t.textContent = l[0];
    });
  })();

  /* ---------- Nút Tạo dự báo: vẽ lại đường dự báo (minh họa) ---------- */
  var btnFc = document.getElementById('btn-forecast');
  if(btnFc) btnFc.addEventListener('click', function(){
    var target = document.getElementById('screen-dubao').querySelector('.banner.green');
    if(target) target.scrollIntoView({behavior: reduced ? 'auto' : 'smooth', block:'center'});
  });

  /* ---------- Dữ liệu lịch sử: tìm kiếm + xuất CSV ---------- */
  var histSearch = document.getElementById('hist-search');
  if(histSearch) histSearch.addEventListener('input', function(){
    var q = histSearch.value.trim().toLowerCase();
    document.querySelectorAll('#hist-table .trow:not(.head)').forEach(function(r){
      r.style.display = (!q || r.textContent.toLowerCase().indexOf(q) !== -1) ? '' : 'none';
    });
  });
  document.getElementById('btn-csv').addEventListener('click', window.EMS.download);
  /* ---------- Cài đặt: lựa chọn, công tắc giảm chuyển động, lưu/hủy ---------- */
  var setStatus = document.getElementById('set-status');
  function markChanged(){ if(setStatus) setStatus.textContent = 'Có thay đổi chưa lưu'; }
  document.querySelectorAll('#density-group .opt').forEach(function(o){
    o.addEventListener('click', function(){
      document.querySelectorAll('#density-group .opt').forEach(function(x){ x.classList.remove('sel'); });
      o.classList.add('sel'); markChanged();
      var rows = document.querySelectorAll('#preview-table .trow');
      rows.forEach(function(r){ r.style.padding = o.getAttribute('data-density') === 'compact' ? '5px 0' : '12px 0'; });
    });
  });
  var motionSwitch = document.getElementById('motion-switch');
  var motionState = document.getElementById('motion-state');
  if(motionSwitch) motionSwitch.addEventListener('click', function(){
    var on = motionSwitch.getAttribute('aria-checked') !== 'true';
    motionSwitch.setAttribute('aria-checked', String(on));
    if(motionState) motionState.textContent = on ? 'Bật' : 'Tắt';
    document.body.classList.toggle('reduce-motion', on);
    markChanged();
  });
  var btnSave = document.getElementById('btn-set-save');
  if(btnSave) btnSave.addEventListener('click', function(){ window.EMS.saveSettings(); if(setStatus) setStatus.textContent = 'Đã lưu trên trình duyệt này'; });
  var btnCancel = document.getElementById('btn-set-cancel');
  if(btnCancel) btnCancel.addEventListener('click', function(){
    if(setStatus) setStatus.textContent = 'Không có thay đổi';
    window.EMS.restoreSettings();
  });
})();
