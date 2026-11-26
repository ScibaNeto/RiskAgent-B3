const fs = require('node:fs');
const template = fs.readFileSync('work/central-template.html', 'utf8');
const snapshot = fs.readFileSync('outputs/Painel-RiskAgent-B3.html', 'utf8').match(/const run=([\s\S]*?);\s*const el=/)[1];
JSON.parse(snapshot);
let page = template.replace('/*DATA*/', () => snapshot);
page = page.replace('</style>', `
.reader{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;margin:-.25rem 0 1rem}.reader select{background:#192925;color:#edf1e9;border:1px solid #668278;border-radius:6px;padding:.32rem .6rem}.guide{border-left:3px solid #c2ed8d;background:#182921;padding:.8rem 1rem;margin:0 0 1rem}.guide h2{font-size:1.05rem;margin:0}.guide p{margin:.3rem 0}.guide summary{cursor:pointer;color:#c2ed8d}.guide summary:focus-visible{outline:2px solid currentColor}.reading-note{color:#dbe6dc}
</style>`);
page = page.replace('<div id="market">','<div class="reader"><label for="reading">Como quer ler o painel?</label><select id="reading"><option value="guided">Leitura guiada</option><option value="technical">Leitura técnica</option></select></div><section class="guide" id="guide"></section><div id="market">');
page = page.replace('window.addEventListener(\'resize\',charts);render();', 'window.addEventListener(\'resize\',charts);');
page = page.replace("function render(){", "function render(){\n updateGuide();");
page = page.replace("charts();}", "if(guided()) $('marketfoot').innerHTML=panel('Quanto o preço caiu desde o ponto mais alto?', '<p>O preço ajustado de PETR4 está '+pct(Math.abs(last.drawdown))+' abaixo do maior fechamento ajustado da série até esse pregão.</p>');charts();}");
page = page.replace("if(view==='Carteira'){", `if(view==='Risco' && guided()) $('detail').innerHTML=panel('Quantas vezes a perda ultrapassou o limite estimado?',table(['Modelo','Dias avaliados','Dias além do limite'],run.tail.filter(r=>r.asset==='PETR4').map(r=>[r.model,r.n,r.breaches]))+'<p>Com um limite de 99% bem calibrado, espera-se cerca de 1 dia além do limite a cada 100 pregões, em média. As perdas nesses dias podem ser maiores.</p>');
 if(view==='Carteira'){`);
page = page.replace("};$('stress').onchange", ";if(guided()) $('type').textContent+=' · Nesse cenário, R$ 1.000,00 passariam a R$ '+f(1000*(1+r.portfolio_simple_pct/100))+'.'};$('stress').onchange");
page = page.replace("dt(last.date);\n for(const", "dt(last.date);\n if(b && guided()) $('period').textContent+=' · Partindo de 100 pontos, PETR4 terminou em '+f(100*last.PETR4/b.PETR4,1)+' e o Ibovespa em '+f(100*last.IBOV/b.IBOV,1)+'.';\n for(const");
page = page.replace('</script></html>', `
function guided(){return $('reading').value==='guided'}
function updateGuide(){
 const change=100*(last.PETR4/prev.PETR4-1);
 const readings={
 Mercado:['O que aconteceu no último dia de negociação?','PETR4 passou de R$ '+f(prev.PETR4)+' para R$ '+f(last.PETR4)+' na série de preços ajustados. O gráfico compara a ação com o Ibovespa, índice que acompanha um conjunto de ações brasileiras.','Pregão é um dia de negociação na bolsa. O gráfico coloca as duas séries em 100 no início do período. Se uma linha chega a 105, ela subiu 5%.','Os cartões usam variação simples entre fechamentos ajustados. O gráfico normaliza cada série pelo primeiro fechamento comum da janela.'],
 PETR4:['Como a ação da Petrobras se saiu?','No último pregão da série, a variação foi de '+pct(change)+'. Escolha um período no gráfico para comparar a ação com o mercado.','PETR4 é o código da ação preferencial da Petrobras. O preço ajustado leva em conta eventos como dividendos para permitir comparações ao longo do tempo.','O retorno simples compara dois preços consecutivos. O retorno logarítmico usa o logaritmo natural da razão entre eles, por isso os percentuais podem diferir.'],
 Risco:['O modelo conseguiu antecipar dias de perda forte?','A tabela conta os pregões em que PETR4 caiu mais do que cada modelo estimava como limite para um dia ruim.','O VaR de 99% estima um limiar de perda diária. O Expected Shortfall estima a perda média nos dias que ultrapassam esse limiar.','Os resultados vêm do teste em dados históricos. A contagem de violações mede frequência. O teste de ES avalia a gravidade das perdas na cauda.'],
 Carteira:['O que aconteceria com R$ 1.000 em um dia difícil?','Imagine R$ 500 em Petrobras e R$ 500 em Vale no início do dia. Escolha um cenário e veja quanto sobraria ao final.','Um cenário histórico usa variações observadas. Um cenário hipotético aplica variações escolhidas para testar a carteira. Nenhum deles prevê o próximo pregão.','O retorno simples da carteira é a média ponderada dos retornos de PETR4 e VALE3, com pesos de 50% antes do choque.'],
 Scanner:['Já existem oportunidades classificadas?','O scanner ainda está em desenvolvimento. A tabela mostra quais informações estão disponíveis para uma futura comparação entre empresas.','Um sinal é uma medida, como a tendência do preço. Vários sinais podem apontar em direções diferentes.','A classificação depende da integração de previsões calibradas, fundamentos e liquidez.'],
 Motores:['Quais partes da plataforma já posso usar?','Comece por Dados financeiros e Risco quantitativo. Cada linha mostra o que a ferramenta faz e o estágio em que ela está.','Em uso indica uma função disponível. Parcial indica que só parte está disponível. Planejado indica trabalho futuro. Protótipo visual permite experimentar a interface.','O roteiro inclui 15 componentes. Os estados abaixo descrevem a cobertura desta prévia local.']
 };
 const [question,summary,definition,method]=readings[view];
 $('guide').innerHTML=guided()?'<h2>'+question+'</h2><p>'+summary+'</p><details><summary>Entenda os termos desta tela</summary><p>'+definition+'</p></details>':'<h2>Como interpretar os resultados</h2><p>'+method+'</p>';
}
try{if(localStorage.getItem('riskagent-reading')==='technical') $('reading').value='technical'}catch{}
$('reading').onchange=()=>{try{localStorage.setItem('riskagent-reading',$('reading').value)}catch{}render()};
render();
</script></html>`);
const priceAverage = fs.readFileSync(require.resolve('../../src/price_average.js'), 'utf8');
page = page.replace('<script>const run=', () => '<script>' + priceAverage + '\nconst run=');
fs.writeFileSync('outputs/Central-RiskAgent.html',page);
