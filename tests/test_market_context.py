from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from src import market_context as m

NOW = datetime(2026, 11, 25, 20, tzinfo=timezone.utc)


def filing():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("itr_2026.csv", "CNPJ_CIA;DT_REFER;VERSAO;DT_RECEB\n" +
            "".join(f"{m.CNPJ};2026-09-30;{v};2026-11-{day}\n" for v,day in [(1,10),(2,26)]))
        header = "CNPJ_CIA;DT_REFER;VERSAO;DT_FIM_EXERC;DT_INI_EXERC;ORDEM_EXERC;MOEDA;ESCALA_MOEDA;CD_CONTA;VL_CONTA\n"
        rows = "".join(f"{m.CNPJ};2026-09-30;{v};2026-09-30;2026-01-01;ÚLTIMO;REAL;MIL;{code};{value}\n"
                       for v in (1,2) for code,value in [("3.01",100),("3.11",20*v)])
        z.writestr("itr_DRE_con_2026.csv",(header+rows).encode("latin1"))
    return buf.getvalue()


class MarketContextTests(unittest.TestCase):
    def test_statement_revision_uses_receipt_and_units(self):
        first = m.statements(filing(), NOW)
        self.assertEqual((first["version"],first["revenue"],first["margin"]),(1,100000,20))
        self.assertEqual(m.statements(filing(),NOW+timedelta(days=1))["margin"],40)

    def test_sgs_excludes_future_and_accepts_deflation(self):
        raw=json.dumps([dict(data="01/10/2026", valor="-0.1"),dict(data="01/12/2026",valor="9")])
        self.assertEqual(m.PARSERS["ipca"](raw,NOW)["rate"],-.1)
        with self.assertRaises(ValueError):
            m.PARSERS["bcb"](raw,NOW)

    def test_news_excludes_future_and_untrusted_links(self):
        record=dict(editorias="economicas",data_publicacao="25/11/2026 15:00:00",titulo="Indicadores",link="https://agenciadenoticias.ibge.gov.br/noticia")
        raw=json.dumps(dict(items=[record,dict(record,link="https://example.com"),dict(record,data_publicacao="25/11/2026 18:00:00",titulo="Futura")]))
        self.assertEqual([r["title"] for r in m.news(raw,NOW)],["Indicadores"])

    def test_version_lookup_and_independent_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def download(url):
                if "cvm.gov" in url: return filing()
                if "bcb.gov" in url: return b'[{"data":"01/10/2026","valor":"2"}]'
                return b'{"items":[]}'
            from unittest.mock import patch
            with patch.object(m, "datetime", wraps=datetime) as clock:
                clock.now.return_value=NOW
                m.refresh(root,download,force=True)
            before=NOW
            self.assertIsNone(m.history(root,"cvm",NOW-timedelta(days=10))["record"])
            for key in m.PARSERS:
                previous=m.history(root,key,before)
                self.assertEqual(previous["record"] is None, key=="ibge")
            with patch.object(m, "datetime", wraps=datetime) as clock:
                clock.now.return_value=NOW+timedelta(seconds=1)
                m.refresh(root,lambda _: b"broken",force=True)
            for key in m.PARSERS:
                current=m.history(root,key,NOW+timedelta(seconds=1))
                self.assertIsNotNone(current["failure"])
                self.assertEqual(current["record"],m.history(root,key,before)["record"])

    def test_regime_and_indicators(self):
        rows=[dict(date=str(i),IBOV=100., PETR4=50.) for i in range(81)]
        self.assertEqual(m.technical(rows)["rsi"],50)
        self.assertEqual(m.technical(rows)["macd"],0)
        self.assertEqual(m.market_regime(rows)["volatility"],0)
        rows[-1].update(IBOV=110.,PETR4=60.)
        self.assertAlmostEqual(m.market_regime(rows)["change"],10)
        self.assertEqual(m.market_regime(rows)["variability"],"acima")
        self.assertEqual(m.technical(rows)["rsi"],100)
        self.assertAlmostEqual(m.technical(rows)["macd"],10*(2/13-2/27))
        rows[-2].update(IBOV=None,PETR4=None)
        self.assertIsNone(m.market_regime(rows))
        self.assertIsNone(m.technical(rows))