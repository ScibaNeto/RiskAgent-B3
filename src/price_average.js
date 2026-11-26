function priceAverage20(history) {
  const window = history.slice(-20);
  if (window.length < 20 || window.some(row => !Number.isFinite(row.PETR4) || row.PETR4 <= 0)) return null;
  return window.reduce((sum, row) => sum + row.PETR4, 0) / 20;
}

function describeAverage20(history) {
  const average = priceAverage20(history);
  if (average === null) return 'Média indisponível. São necessários 20 pregões consecutivos com preços válidos.';
  const format = value => value.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const close = history.at(-1).PETR4;
  const comparison = close > average ? 'acima da' : close < average ? 'abaixo da' : 'igual à';
  return 'O fechamento ajustado de R$ ' + format(close) + ' ficou ' + comparison +
    ' média dos últimos 20 pregões (R$ ' + format(average) + ').';
}
