const NS='http://www.w3.org/2000/svg';
const fmt=(v)=>Number(v).toLocaleString('vi-VN',{maximumFractionDigits:1});
const dateLabel=(time)=>time.slice(8,10)+'/'+time.slice(5,7)+' '+time.slice(11,16);
const svgNode=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;};

export function timeChart(host,rows,series,{unit='Cuộc gọi / giờ',cursor=null,limit=null,onHover=null,height=310}={}) {
  host.replaceChildren();
  const svg=svgNode('svg',{class:'series-chart',role:'img',tabindex:'0','aria-label':`${unit} theo thời gian. Dùng phím mũi tên để đọc từng giờ. Bảng dữ liệu có ở phía dưới.`});
  const tooltip=document.createElement('div');tooltip.className='chart-tooltip';tooltip.hidden=true;tooltip.setAttribute('role','status');
  host.append(svg,tooltip);
  let selected=Math.min(cursor??Math.floor(rows.length/2),rows.length-1),geometry;
  function draw(){
    const width=Math.max(240,host.clientWidth-parseFloat(getComputedStyle(host).paddingLeft)-parseFloat(getComputedStyle(host).paddingRight));
    const H=height,left=43,right=18,top=38,bottom=42,plotW=width-left-right,plotH=H-top-bottom;
    const values=series.flatMap(s=>rows.map((r,i)=>s.value(r,i)).filter(v=>v!==null&&Number.isFinite(v)));
    if(limit!==null)values.push(limit);
    const maximum=Math.max(5,...values)*1.12,step=maximum<=12?2:maximum<=40?5:Math.ceil(maximum/25)*5,ceiling=Math.ceil(maximum/step)*step;
    const x=i=>left+i/Math.max(1,rows.length-1)*plotW,y=v=>top+(1-v/ceiling)*plotH;
    geometry={width,H,left,right,top,bottom,x,y};svg.setAttribute('viewBox',`0 0 ${width} ${H}`);svg.replaceChildren();
    svg.append(svgNode('title',{},`${unit}. ${rows.length} giờ dữ liệu.`),svgNode('text',{x:left,y:16},unit));
    if(cursor!==null&&cursor<rows.length){const cx=x(cursor);svg.append(svgNode('rect',{x:cx,y:top,width:Math.max(0,width-right-cx),height:plotH,fill:'#edf3f6'}));if(width-cx>130)svg.append(svgNode('text',{x:cx+12,y:top+19},'Chưa mở quan sát'));}
    for(let v=0;v<=ceiling;v+=step){svg.append(svgNode('line',{x1:left,x2:width-right,y1:y(v),y2:y(v),class:'plot-grid'}),svgNode('text',{x:left-9,y:y(v)+4,'text-anchor':'end'},fmt(v)));}
    const ticks=width<430?4:7;
    for(let t=0;t<ticks;t++){const i=Math.round(t/(ticks-1)*(rows.length-1));const label=rows.length<=24?rows[i].time.slice(11,16):dateLabel(rows[i].time);svg.append(svgNode('text',{x:x(i),y:H-14,'text-anchor':t===0?'start':t===ticks-1?'end':'middle'},label));}
    if(limit!==null){svg.append(svgNode('line',{x1:left,x2:width-right,y1:y(limit),y2:y(limit),stroke:'#b55240','stroke-dasharray':'5 4'}),svgNode('text',{x:width-right,y:y(limit)-7,'text-anchor':'end'},`Hiện có ${limit} xe`));}
    for(const s of series){let path='',active=false;rows.forEach((r,i)=>{const v=s.value(r,i);if(v===null||!Number.isFinite(v)){active=false;return;}path+=(active?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2);active=true;});svg.append(svgNode('path',{d:path,fill:'none',stroke:s.color,'stroke-width':s.width??2.3,'stroke-dasharray':s.dash??'','stroke-linejoin':'round','stroke-linecap':'round'}));if(rows.length<=48)rows.forEach((r,i)=>{const v=s.value(r,i);if(v!==null&&Number.isFinite(v))svg.append(svgNode('circle',{cx:x(i),cy:y(v),r:2.7,fill:s.color}));});}
    if(cursor!==null&&cursor<rows.length){const cx=x(cursor);svg.append(svgNode('line',{x1:cx,x2:cx,y1:top,y2:H-bottom,stroke:'#627588','stroke-dasharray':'4 3'}),svgNode('text',{x:Math.min(cx+6,width-right-60),y:top-9},rows[cursor].time.slice(11,16)));}
    const guide=svgNode('line',{class:'crosshair',y1:top,y2:H-bottom,visibility:'hidden'});svg.append(guide);
    const markers=series.map(s=>{const n=svgNode('circle',{r:4,fill:s.color,visibility:'hidden'});svg.append(n);return n;});
    const overlay=svgNode('rect',{x:left,y:top,width:plotW,height:plotH,fill:'transparent','aria-hidden':'true'});svg.append(overlay);
    function reveal(index,event){selected=Math.max(0,Math.min(rows.length-1,index));const row=rows[selected];guide.setAttribute('x1',x(selected));guide.setAttribute('x2',x(selected));guide.setAttribute('visibility','visible');tooltip.replaceChildren();const title=document.createElement('strong');title.textContent=dateLabel(row.time);tooltip.append(title);
      series.forEach((s,i)=>{const v=s.value(row,selected);markers[i].setAttribute('visibility',v===null?'hidden':'visible');if(v===null)return;markers[i].setAttribute('cx',x(selected));markers[i].setAttribute('cy',y(v));const line=document.createElement('div');line.className='tooltip-row';const label=document.createElement('span'),value=document.createElement('span');label.textContent=s.label;value.textContent=fmt(v);line.append(label,value);tooltip.append(line);});
      if(!tooltip.children[1]){tooltip.hidden=true;return;}tooltip.hidden=false;const box=host.getBoundingClientRect();const px=event?event.clientX-box.left:x(selected);tooltip.style.left=Math.max(5,Math.min(host.clientWidth-tooltip.offsetWidth-5,px+14))+'px';tooltip.style.top='35px';if(onHover)onHover(selected,row);
    }
    overlay.onpointermove=e=>{const box=svg.getBoundingClientRect();const px=(e.clientX-box.left)/box.width*width;reveal(Math.round((px-left)/plotW*(rows.length-1)),e);};
    overlay.onpointerleave=()=>{tooltip.hidden=true;guide.setAttribute('visibility','hidden');markers.forEach(m=>m.setAttribute('visibility','hidden'));};
    overlay.onclick=e=>overlay.onpointermove(e);
    svg.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();reveal(selected+(e.key==='ArrowRight'?1:-1));}};
  }
  draw();const observer=new ResizeObserver(()=>draw());observer.observe(host);
  return ()=>{observer.disconnect();host.replaceChildren();};
}

export function heatmap(host,rows){
  host.replaceChildren();const groups=Array.from({length:7},()=>Array.from({length:24},()=>[]));
  for(const r of rows){const d=new Date(r.time+'Z');groups[(d.getUTCDay()+6)%7][d.getUTCHours()].push(r.actual);}
  const means=groups.map(d=>d.map(v=>v.length?v.reduce((a,b)=>a+b,0)/v.length:null)),maximum=Math.max(1,...means.flat().filter(v=>v!==null));
  const grid=document.createElement('div');grid.className='heatmap';grid.setAttribute('role','img');grid.setAttribute('aria-label','Trung bình số cuộc gọi theo thứ và giờ trong tập test.');
  const label=(s)=>{const n=document.createElement('span');n.className='heat-label';n.textContent=s;grid.append(n);};label('');for(let h=0;h<24;h++)label(h%6===0?h+'h':'');
  means.forEach((day,i)=>{label(['T2','T3','T4','T5','T6','T7','CN'][i]);day.forEach((v,h)=>{const n=document.createElement('div');n.className='heat-cell';n.style.opacity=v===null?.05:String(.13+.87*v/maximum);const text=`${['Thứ 2','Thứ 3','Thứ 4','Thứ 5','Thứ 6','Thứ 7','Chủ nhật'][i]}, ${h} giờ: ${v===null?'chưa có dữ liệu':fmt(v)+' cuộc gọi/giờ'}`;n.dataset.label=text;n.setAttribute('aria-label',text);grid.append(n);});});host.append(grid);
}
