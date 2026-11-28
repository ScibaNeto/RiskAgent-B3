function drawSeries(canvas, points, curves, markBreaches) {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const values = points.flatMap(row => curves.map(curve => row[curve.key])).filter(Number.isFinite);
  if (!values.length) {
    ctx.fillText('Sem valores no período.', 18, 35);
    return;
  }
  const low = Math.min(...values), high = Math.max(...values);
  const x = i => 56 + i * (width - 73) / Math.max(points.length - 1, 1);
  const y = v => 15 + (high - v) * (height - 50) / (high - low || 1);
  ctx.font = '12px system-ui';
  ctx.fillStyle = '#b4bab9';
  for (let k = 0; k <= 3; k++) {
    const value = low + k * (high - low) / 3;
    ctx.fillText(num(value,1), 4, y(value) + 4);
    ctx.strokeStyle = '#333437';
    ctx.beginPath(); ctx.moveTo(50,y(value)); ctx.lineTo(width-10,y(value)); ctx.stroke();
  }
  ctx.fillText(points[0].date.split('-').reverse().join('/'), 54,height-8);
  if(points.length>1) {
    ctx.textAlign='right';
    ctx.fillText(points.at(-1).date.split('-').reverse().join('/'),width-10,height-8);
    ctx.textAlign='left';
  }
  for(const {key,color} of curves) {
    ctx.strokeStyle=color; ctx.lineWidth=1.7; ctx.beginPath();
    let connected=false;
    points.forEach((row,i)=>{
      if(!Number.isFinite(row[key])) {connected=false;return;}
      if(connected) ctx.lineTo(x(i),y(row[key]));
      else ctx.moveTo(x(i),y(row[key]));
      connected=true;
    });
    ctx.stroke();
    if(points.length===1 && Number.isFinite(points[0][key])){
      ctx.fillStyle=color;ctx.fillRect(x(0)-2,y(points[0][key])-2,4,4);
    }
  }
  if(markBreaches){
    ctx.fillStyle='#ff9592';
    points.forEach((row,i)=>{
      if(Number.isFinite(row.var_pct) && Number.isFinite(row.return_pct) && row.return_pct<row.var_pct){
        ctx.beginPath();ctx.arc(x(i),y(row.return_pct),3,0,2*Math.PI);ctx.fill();
      }
    });
  }
}

function setupAssetView(history){
  if(!history.length){el('petro').hidden=true;return;}
  const cut=el('cut'), span=el('span');
  cut.min=history[0].date;cut.max=history.at(-1).date;cut.value=cut.max;
  const valueText=n=>Number.isFinite(n)?fmt(n):'indisponível';
  function render(){
    if(!cut.value || !cut.validity.valid){
      el('pricesummary').textContent='Selecione uma data dentro do histórico.';
      el('average20').textContent='';el('riskday').textContent='';el('drawdown').textContent='—';
      for(const id of ['riskplot','performance'])el(id).width=el(id).width;
      return;
    }
    const past=history.filter(r=>r.date<=cut.value);
    el('average20').textContent=describeAverage20(past);
    const count=Number(span.value);
    const period=count?past.slice(-count):past;
    const first=period.findIndex(r=>Number.isFinite(r.PETR4)&&Number.isFinite(r.IBOV));
    const base=period[first];
    const chart=period.map((r,i)=>({...r,
      petr:i>=first && base && Number.isFinite(r.PETR4)?100*r.PETR4/base.PETR4:null,
      ibov:i>=first && base && Number.isFinite(r.IBOV)?100*r.IBOV/base.IBOV:null}));
    const last=chart.at(-1);
    const day=last.date.split('-').reverse().join('/');
    const indexText=v=>Number.isFinite(v)?num(v,2):'indisponível';
    el('pricesummary').textContent=day+' · PETR4 (verde) '+indexText(last.petr)+' · Ibovespa (marrom) '+indexText(last.ibov);
    el('drawdown').textContent=valueText(last.drawdown);
    drawSeries(el('performance'),chart,[{key:'petr',color:'#87c8a8'},{key:'ibov',color:'#d6aa8b'}],false);
    drawSeries(el('riskplot'),period,[{key:'return_pct',color:'#87c8a8'},{key:'var_pct',color:'#d6aa8b'}],true);
    const available=Number.isFinite(last.return_pct)&&Number.isFinite(last.var_pct);
    const status=available?(last.return_pct<last.var_pct?'Perda acima do VaR.':'Dentro do limite previsto.'):'Comparação indisponível neste pregão.';
    el('riskday').textContent=day+' · Retorno '+valueText(last.return_pct)+' · VaR '+valueText(last.var_pct)+'. '+status;
  }
  cut.addEventListener('input',render);span.addEventListener('change',render);
  window.addEventListener('resize',render);render();
}
setupAssetView(run.history);
