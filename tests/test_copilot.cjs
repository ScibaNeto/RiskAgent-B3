const assert=require('node:assert/strict');
const {consultSnapshot:ask}=require('../src/copilot.js');
const run={run:'a',history:[{date:'2026-11-26',PETR4:43.19}],scanner:{
  run:'a',date:'2026-11-26',expected:'2026-11-26',cards:[
    {asset:'PETR4',var:-3,realized:-4,status:'Sinais conflitantes',missing:[],conflicts:['Perda excedente.']}
  ]}};
assert.match(ask(run,'close','PETR4').text,/43,19/);
assert.match(ask(run,'risk','PETR4').text,/perda ultrapassou/i);
assert.match(ask(run,'screen','PETR4').text,/Perda excedente/);
assert.equal(ask(run,'risk','VALE3').source,null);
assert.equal(ask(run,'close','VALE3').source,null);
run.scanner.run='outro';
assert.equal(ask(run,'screen','PETR4').source,null);
