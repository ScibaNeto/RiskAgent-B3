const assert=require('node:assert/strict');
const {simulatePortfolio:simulate,portfolioSample:sample}=require('../src/portfolio_lab.js');
const row=(date,a,b,index=100)=>({date,PETR4:a,VALE3:b,IBOV:index});
const rows=[row('2026-01-29',100,100),row('2026-01-30',200,100),row('2026-02-02',200,200),row('2026-02-03',200,100)];
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-8,`${a} vs ${b}`);
const hold=simulate(rows,.5,'hold',10);
close(hold.equity,1500);close(hold.fees,0);close(hold.weight,2/3);
const daily=simulate(rows,.5,'daily',0);
close(daily.equity,1687.5);close(daily.drawdown,-.25);assert.equal(daily.trades,2);
const monthly=simulate(rows,.5,'monthly',100);
close(monthly.traded,1/3);close(monthly.fees,5);close(monthly.equity,1495);
assert.equal(monthly.trades,1);
for(const w of [0,1]){
  const x=simulate(rows,w,'daily',100);
  close(x.weight,w);close(x.traded,0);close(x.equity,w?2000:1000);
}
assert.equal(simulate([rows[0]],.5,'daily',10),null);
assert.equal(sample(rows,'2026-01-30',252).length,2);
assert.equal(sample([rows[0],row('2026-01-30',null,100),...rows.slice(2)],'2026-02-03',252).length,2);
assert.equal(sample(rows,'2026-02-03',2).length,3);
assert.ok(daily.correlation<0);
assert.throws(()=>simulate(rows,1.5,'daily',10));