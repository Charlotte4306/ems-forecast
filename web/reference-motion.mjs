// Small, user-triggered feedback inspired by the reference's press effects.
// Never animate or scramble forecast values, timestamps or measurement labels.
export function installReferenceMotion(){
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  document.addEventListener('click',event=>{
    if(reduced.matches||document.body.classList.contains('reduce-motion'))return;
    const button=event.target.closest('.ops-flow button,.btn-primary');
    if(!button||button.disabled)return;
    const box=button.getBoundingClientRect();
    const x=event.detail?event.clientX:box.left+box.width/2;
    const y=event.detail?event.clientY:box.top+box.height/2;
    for(let i=0;i<5;i++){
      const dot=document.createElement('span');dot.className='ops-press-dot';dot.setAttribute('aria-hidden','true');
      dot.style.left=x+'px';dot.style.top=y+'px';dot.style.background=i%2?'var(--accent)':'var(--glass-border)';
      const angle=Math.PI*2*i/5;dot.style.setProperty('--dx',Math.cos(angle)*25+'px');dot.style.setProperty('--dy',Math.sin(angle)*25+'px');
      document.body.append(dot);setTimeout(()=>dot.remove(),500);
    }
  });
}
