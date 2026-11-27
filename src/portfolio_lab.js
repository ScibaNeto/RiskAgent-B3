// Simulation from consecutive B3 closes. Fractional positions, self-financing trades.
function portfolioSample(history, end, length) {
  const available = history.filter(row => row.date <= end);
  let first = available.length;
  while (first > 0 && ['PETR4','VALE3','IBOV'].every(key =>
    Number.isFinite(available[first-1][key]) && available[first-1][key] > 0)) first--;
  const segment = available.slice(first);
  return length ? segment.slice(-(length+1)) : segment;
}

function simulatePortfolio(rows, target, policy, bps) {
  if (rows.length < 2) return null;
  if (!(target >= 0 && target <= 1 && bps >= 0 && bps <= 100) ||
      !['daily','monthly','hold'].includes(policy)) throw Error('Configuração inválida.');
  const fee = bps / 10000;
  let equity = 1000, gross = 1000, weight = target, traded = 0, fees = 0, trades = 0;
  let peak = equity, drawdown = 0, meanA = 0, meanB = 0, cov = 0, va = 0, vb = 0;
  const path = [{date:rows[0].date, equity, index:1000}];
  for(let i=1;i<rows.length;i++) {
    const a=rows[i-1], b=rows[i];
    const ra=b.PETR4/a.PETR4-1, rb=b.VALE3/a.VALE3-1;
    const rebalance=policy==='daily' || (policy==='monthly' && a.date.slice(0,7)!==b.date.slice(0,7));
    if(rebalance && Math.abs(weight-target)>1e-12) {
      // Fraction of pre-trade wealth paid in fees. Buy/sell directions are opposite.
      const sign=Math.sign(target-weight);
      const cost=2*fee*Math.abs(target-weight)/(1+sign*fee*(2*target-1));
      const turnover=Math.abs(target*(1-cost)-weight)+Math.abs((1-target)*(1-cost)-(1-weight));
      traded+=turnover; fees+=equity*cost; equity*=1-cost; weight=target; trades++;
    }
    const growth=weight*(1+ra)+(1-weight)*(1+rb);
    equity*=growth; gross*=growth;
    weight=weight*(1+ra)/growth;
    peak=Math.max(peak,equity); drawdown=Math.min(drawdown,equity/peak-1);
    const da=ra-meanA, db=rb-meanB;
    meanA+=da/i;meanB+=db/i;
    cov+=da*(rb-meanB);va+=da*(ra-meanA);vb+=db*(rb-meanB);
    path.push({date:b.date,equity,index:1000*b.IBOV/rows[0].IBOV});
  }
  return {equity,gross,fees,traded,trades,drawdown,weight,path,
          correlation:va>0 && vb>0 ? cov/Math.sqrt(va*vb) : null};
}

function setupPortfolioLab(history) {
  const element=id=>document.getElementById('lab-'+id);
  if(!history.length){element('summary').textContent='Histórico indisponível.';return}
  const date=element('date');
  date.min=history[0].date;date.max=history.at(-1).date;date.value=date.max;
  const money=v=>v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
  const percent=v=>(100*v).toLocaleString('pt-BR',{maximumFractionDigits:2})+'%';
  function render(){
    const w=Number(element('weight').value)/100, fee=element('fee');
    element('weights').textContent=percent(w)+' PETR4 · '+percent(1-w)+' VALE3';
    const sample=portfolioSample(history,date.value,Number(element('period').value));
    const simulation=date.value && date.validity.valid && fee.value!=='' && fee.validity.valid ?
      simulatePortfolio(sample,w,element('policy').value,Number(fee.value)) : null;
    element('facts').textContent='';element('stress').textContent='';
    if(!simulation){element('summary').textContent='Escolha uma data com dois fechamentos consecutivos e um custo entre 0 e 100 pontos-base.';return}
    const x=simulation, last=x.path.at(-1);
    element('summary').textContent='De '+localDate(sample[0].date)+' a '+localDate(last.date)+', R$ 1.000,00 passaram a '+money(x.equity)+' após custos ('+percent(x.equity/1000-1)+'). No Ibovespa, o valor equivalente foi '+money(last.index)+'.';
    element('facts').textContent=(sample.length-1)+' pregões consecutivos · Saldo bruto '+money(x.gross)+' · Custos pagos '+money(x.fees)+' · '+x.trades+' rebalanceamentos · Volume negociado acumulado em proporção do patrimônio: '+percent(x.traded)+' · Maior queda desde um pico: '+percent(x.drawdown)+' · Correlação diária PETR4/VALE3: '+(x.correlation===null?'indisponível':x.correlation.toFixed(2).replace('.',','))+'.';
    element('stress').textContent='Peso final em PETR4: '+percent(x.weight)+'. Se no próximo pregão PETR4 caísse 10% e VALE3 subisse 5%, antes de novo rebalanceamento, a carteira variaria '+percent(-.1*x.weight+.05*(1-x.weight))+'.';
  }
  for(const id of ['date','period','policy','weight','fee']) element(id).addEventListener('input',render);
  render();
}
if(typeof module!=='undefined' && module.exports) module.exports={portfolioSample,simulatePortfolio};
