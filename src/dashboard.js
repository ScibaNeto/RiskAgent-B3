(() => {
  const links = Array.from(document.querySelectorAll('.nav-inner a'));
  const sections = document.querySelectorAll('main > section');
  const titles = Object.fromEntries(links.map(a=>[a.hash.slice(1), a.textContent]));
  const history = run.history;
  const names = {PETR4:'Petrobras', VALE3:'Vale', IBOV:'Ibovespa'};
  const price = (key,v) => !Number.isFinite(v)?'—':key==='IBOV'?num(v,0)+' pts':'R$ '+num(v,2);
  const last = history.at(-1) || {}, prev = history.at(-2) || {};
  let key='PETR4', length=63;
  const buttons = new Map(), ranges=new Map();
  for(const ticker of Object.keys(names)){
    const button=document.createElement('button');
    button.type='button';button.className='ticker';
    button.innerHTML='<span class="tile"></span><span><b></b><small></small></span><b class="last"></b>';
    button.querySelector('.tile').textContent=ticker==='IBOV'?'IB':ticker.slice(0,2);
    button.querySelector('b').textContent=ticker;
    button.querySelector('small').textContent=names[ticker];
    button.querySelector('.last').textContent=price(ticker,last[ticker]);
    button.onclick=()=>{key=ticker;draw()};
    buttons.set(ticker,button);el('watchlist').append(button);
  }
  for(const [n,label] of [[21,'1M'],[63,'3M'],[126,'6M'],[252,'1A']]){
    const button=document.createElement('button');button.textContent=label;
    button.setAttribute('aria-label',n+' pregões');button.onclick=()=>{length=n;draw()};
    ranges.set(n,button);document.querySelector('.periods').append(button);
  }
  function draw(){
    if(el('overview').classList.contains('page-off'))return;
    for(const [n,b] of ranges)b.setAttribute('aria-pressed',String(n===length));
    for(const [k,b] of buttons)b.setAttribute('aria-pressed',String(k===key));
    el('focus-label').textContent=names[key]+' · '+key;
    el('focus-price').textContent=price(key,last[key]);
    const delta=Number.isFinite(last[key]) && prev[key]>0?(last[key]/prev[key]-1)*100:null;
    const change=el('focus-change');
    change.textContent=delta===null?'':(delta>=0?'+':'')+fmt(delta)+' no pregão';
    change.className='delta '+(delta>=0?'positive':'negative');
    el('focus-unit').textContent=key==='IBOV'?'Fechamento do índice':'Fechamento ajustado por ação';
    const rows=history.slice(-length);
    el('focus-start').textContent=rows.length?localDate(rows[0].date):'';
    el('focus-end').textContent=last.date?localDate(last.date):'';
    const c=el('focus-chart'),w=c.clientWidth,h=c.clientHeight,ratio=window.devicePixelRatio||1;
    if(!w || !h)return;
    c.width=w*ratio;c.height=h*ratio;const g=c.getContext('2d');g.scale(ratio,ratio);
    c.setAttribute('aria-label','Histórico de '+key+' em '+rows.length+' pregões. Último fechamento: '+price(key,last[key]));
    const vals=rows.map(r=>r[key]).filter(Number.isFinite);
    if(!vals.length){g.fillStyle='#ddd';g.fillText('Histórico indisponível',8,22);return}
    const min=Math.min(...vals),max=Math.max(...vals),left=0,right=w-52,top=10,bottom=h-12;
    g.font='11px Segoe UI, sans-serif';g.textBaseline='middle';
    for(let j=0;j<=3;j++){
      const y=top+(bottom-top)*j/3;
      g.strokeStyle='#3c3d3d';g.lineWidth=1;g.beginPath();g.moveTo(left,y);g.lineTo(right,y);g.stroke();
      g.fillStyle='#a9abaa';g.fillText(num(max-(max-min)*j/3,key==='IBOV'?0:2),right+5,y);
    }
    g.strokeStyle=getComputedStyle(c).getPropertyValue('--brand-light').trim();g.lineWidth=2.4;g.beginPath();let connected=false;
    rows.forEach((r,i)=>{
      if(!Number.isFinite(r[key])){connected=false;return}
      const x=left+i*(right-left)/Math.max(1,rows.length-1);
      const y=max===min?(top+bottom)/2:top+(max-r[key])*(bottom-top)/(max-min);
      if(connected)g.lineTo(x,y);else g.moveTo(x,y);connected=true;
    });
    g.stroke();
  }
  function navigate(){
    const hash=location.hash.slice(1);
    const page=titles[hash]?hash:(document.getElementById(hash)?.closest('section')?.dataset.page || 'overview');
    for(const section of sections)section.classList.toggle('page-off',(section.dataset.page||section.id)!==page);
    for(const link of links){if(link.hash==='#'+page)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current')}
    el('page-title').textContent=titles[page];
    document.title=titles[page]+' · RiskAgent B3';
    window.scrollTo(0,0);
    window.dispatchEvent(new Event('resize'));
  }
  el('brief-result').textContent=el('scan-summary').textContent;
  window.addEventListener('resize',draw);
  window.addEventListener('hashchange',navigate);
  navigate();
})();