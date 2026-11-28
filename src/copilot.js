function consultSnapshot(run, topic, asset) {
  const unavailable = {text:'Esta consulta está indisponível nesta execução.', source:null, page:null};
  if (!['PETR4','VALE3'].includes(asset) || !run.run) return unavailable;
  const format = n => n.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
  const last = run.history?.at(-1);
  if(topic==='close' && last?.date && Number.isFinite(last[asset])) {
    return {text:'O fechamento ajustado de '+asset+' foi R$ '+format(last[asset])+'.',
      date:last.date,source:'Snapshot de preços ajustados',page:'overview'};
  }
  const scanner = run.scanner;
  if (!scanner?.date || scanner.run!==run.run) return unavailable;
  const card = scanner.cards.find(c=>c.asset===asset);
  if (!card) return unavailable;
  const coverage = scanner.date!==scanner.expected?' O último pregão esperado era '+scanner.expected+'.':'';
  if(topic==='risk' && Number.isFinite(card.realized) && Number.isFinite(card.var) && card.var<0) {
    const outcome=card.realized<card.var?'A perda ultrapassou':'O retorno ficou acima ou no nível de';
    return {text:asset+' teve retorno logarítmico de '+format(card.realized)+'%. '+outcome+
      ' um limite de risco estimado em '+format(card.var)+'% (VaR diário de 99%).'+coverage,
      date:scanner.date,source:'Backtest GJR-GARCH-t',page:'risco'};
  }
  if(topic==='screen') {
    const reasons=[...card.missing,...card.conflicts];
    if(!reasons.length && Number.isFinite(card.momentum) && Number.isFinite(card.relative))
      reasons.push('Em 20 pregões, a variação foi '+format(card.momentum)+'% e a diferença para o Ibovespa foi '+format(card.relative)+' pontos percentuais.');
    return {text:asset+' · '+card.status+'. '+reasons.join(' ')+coverage,
      date:scanner.date,source:'Ficha de triagem da execução',page:'scanner'};
  }
  return unavailable;
}

function setupCopilot(run) {
  const get=id=>document.getElementById(id);
  function show(){
    const result=consultSnapshot(run,get('copilot-topic').value,get('copilot-asset').value);
    get('copilot-answer').textContent=result.text;
    get('copilot-source').textContent=result.source?result.source+' · '+result.date.split('-').reverse().join('/')+' · '+run.run:'';
    const link=get('copilot-link');
    link.hidden=!result.page;
    if(result.page) link.href='#'+result.page;
  }
  get('copilot-asset').onchange=show;get('copilot-topic').onchange=show;show();
}
if(typeof module!=='undefined' && module.exports) module.exports={consultSnapshot};
