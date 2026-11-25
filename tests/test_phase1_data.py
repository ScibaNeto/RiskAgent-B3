import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import var_baseline as phase1
from b3_sessions import completed_sessions


def price_fixture(count: int, end: pd.Timestamp | None = None) -> pd.Series:
    """Pequena fixture deterministica para testar limpeza e contagem, nao mercado."""
    dates = completed_sessions("2010-01-01", pd.Timestamp.now(tz="UTC"))
    if end is not None:
        dates = dates[dates <= end]
    dates = dates[-count:]
    values = 100.0 * np.exp(np.arange(count, dtype=float) * 0.0001)
    return pd.Series(values, index=dates, name="PETR4")


class Phase1DataTests(unittest.TestCase):
    def test_amostra_insuficiente(self):
        with self.assertRaisesRegex(RuntimeError, "1249 retornos validos"):
            phase1.validar_amostra(pd.Series(np.zeros(phase1.MIN_RETURNS - 1)))

    def test_amostra_exatamente_no_limite(self):
        phase1.validar_amostra(pd.Series(np.zeros(phase1.MIN_RETURNS)))

    def test_amostra_acima_do_limite(self):
        phase1.validar_amostra(pd.Series(np.zeros(phase1.MIN_RETURNS + 1)))

    def test_1251_precos_produzem_1250_retornos(self):
        prices = price_fixture(phase1.MIN_RETURNS + 1)
        returns = phase1._calcular_retornos(prices, "PETR4")
        self.assertEqual(len(returns), phase1.MIN_RETURNS)
        phase1.validar_amostra(returns, "PETR4")

    def test_datas_ausentes_e_precos_invalidos_reduzem_a_amostra(self):
        prices = price_fixture(phase1.MIN_RETURNS + 2)
        prices.iloc[100] = np.nan
        prices.iloc[200] = 0.0
        cleaned = phase1._normalizar_precos(prices, "PETR4")
        returns = phase1._calcular_retornos(cleaned, "PETR4")
        self.assertEqual(len(cleaned), phase1.MIN_RETURNS)
        self.assertEqual(len(returns), phase1.MIN_RETURNS - 3)
        with self.assertRaises(RuntimeError):
            phase1.validar_amostra(returns, "PETR4")

    def test_duplicidades_sao_removidas_e_datas_ordenadas(self):
        prices = price_fixture(phase1.MIN_RETURNS + 1)
        shuffled = pd.concat([prices.iloc[::-1], prices.iloc[[0]]])
        cleaned = phase1._normalizar_precos(shuffled, "PETR4")
        self.assertTrue(cleaned.index.is_monotonic_increasing)
        self.assertFalse(cleaned.index.has_duplicates)
        self.assertEqual(len(cleaned), phase1.MIN_RETURNS + 1)
        self.assertEqual(len(phase1._calcular_retornos(cleaned, "PETR4")), phase1.MIN_RETURNS)

    def test_datas_futuras_e_invalidas_sao_rejeitadas(self):
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        prices = pd.Series([10.0, 11.0, 12.0], index=[today, today + pd.Timedelta(days=1), pd.NaT])
        cleaned = phase1._normalizar_precos(prices, "PETR4")
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned.index[0], today)

    def test_download_vazio_preserva_cache_valido(self):
        prices = price_fixture(phase1.MIN_RETURNS + 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            cache_path = data_dir / "PETR4.csv"
            prices.to_csv(cache_path)
            before = cache_path.read_bytes()
            with patch.object(phase1, "DADOS", data_dir), patch.object(
                phase1, "_baixar_yahoo", return_value=pd.Series(dtype=float)
            ), patch("time.sleep"):
                actual = phase1.baixar_retornos("PETR4", "PETR4.SA", tentativas=2)
            self.assertEqual(len(actual), phase1.MIN_RETURNS)
            self.assertEqual(cache_path.read_bytes(), before)


    def test_download_invalido_preserva_cache_valido(self):
        prices = price_fixture(phase1.MIN_RETURNS + 1)
        bad_download = pd.Series(
            [0.0, np.nan],
            index=[prices.index[-1], prices.index[-1] - pd.Timedelta(days=1)],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            cache_path = data_dir / "PETR4.csv"
            prices.to_csv(cache_path)
            before = cache_path.read_bytes()
            with patch.object(phase1, "DADOS", data_dir), patch.object(
                phase1, "_baixar_yahoo", return_value=bad_download
            ), patch("time.sleep"):
                actual = phase1.baixar_retornos("PETR4", "PETR4.SA", tentativas=1)
            self.assertEqual(len(actual), phase1.MIN_RETURNS)
            self.assertEqual(cache_path.read_bytes(), before)

    def test_atualizacao_incremental_sobrepoe_dias_e_acrescenta_dados(self):
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        full = price_fixture(phase1.MIN_RETURNS + 10, end=today)
        cached = full.iloc[: phase1.MIN_RETURNS + 1]
        overlap_day = cached.index[-1]
        download = full.loc[cached.index[-1] - pd.Timedelta(days=phase1.CACHE_OVERLAP_DAYS) :].copy()
        download.loc[overlap_day] *= 1.01  # revisao do provedor dentro da sobreposicao
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            cache_path = data_dir / "PETR4.csv"
            cached.to_csv(cache_path)
            with patch.object(phase1, "DADOS", data_dir), patch.object(
                phase1, "_baixar_yahoo", return_value=download
            ) as downloader:
                actual = phase1.baixar_retornos("PETR4", "PETR4.SA", tentativas=1)
            expected_start = (cached.index[-1] - pd.Timedelta(days=phase1.CACHE_OVERLAP_DAYS)).strftime("%Y-%m-%d")
            downloader.assert_called_once_with("PETR4.SA", start=expected_start)
            self.assertEqual(actual.index.max(), full.index[-1])
            saved = pd.read_csv(cache_path, index_col=0, parse_dates=True).iloc[:, 0]
            self.assertAlmostEqual(saved.loc[overlap_day], download.loc[overlap_day])

    def test_cache_curto_solicita_historico_completo(self):
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        short_cache = price_fixture(100, end=today - pd.Timedelta(days=100))
        complete_history = price_fixture(phase1.MIN_RETURNS + 1, end=today)
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            short_cache.to_csv(data_dir / "PETR4.csv")
            with patch.object(phase1, "DADOS", data_dir), patch.object(
                phase1, "_baixar_yahoo", return_value=complete_history
            ) as downloader:
                actual = phase1.baixar_retornos("PETR4", "PETR4.SA", tentativas=1)
            downloader.assert_called_once_with("PETR4.SA", start=phase1.INICIO)
            self.assertEqual(len(actual), phase1.MIN_RETURNS)

    def test_modo_estrito_recusa_cache_antigo(self):
        old_end = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=10)
        prices = price_fixture(phase1.MIN_RETURNS + 1, end=old_end)
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            cache_path = data_dir / "PETR4.csv"
            prices.to_csv(cache_path)
            before = cache_path.read_bytes()
            with patch.object(phase1, "DADOS", data_dir), patch.object(
                phase1, "_baixar_yahoo", return_value=pd.Series(dtype=float)
            ), patch("time.sleep"):
                with self.assertRaisesRegex(RuntimeError, "Modo estrito"):
                    phase1.baixar_retornos("PETR4", "PETR4.SA", tentativas=1, strict_cache=True)
            self.assertEqual(cache_path.read_bytes(), before)


class Phase1GarchConvergenceTests(unittest.TestCase):
    def test_nonconverged_blocks_are_unavailable_and_diagnosed(self):
        returns = pd.Series(np.linspace(-1.0, 1.0, 6), index=pd.date_range("2020-01-01", periods=6))

        class FitResult:
            convergence_flag = 1
            params = pd.Series({"nu": 8.0})
            loglikelihood = -10.0
            optimization_result = SimpleNamespace(nit=7)

        class Model:
            def fit(self, **kwargs):
                return FitResult()

        with patch.object(phase1, "JANELA", 3), patch.object(phase1, "REESTIMAR_A_CADA", 2), patch.object(
            phase1, "arch_model", side_effect=lambda *_args, **_kwargs: Model()
        ):
            forecasts, diagnostics = phase1.var_gjr_garch_t(returns, "TEST")

        self.assertEqual(len(diagnostics), 2)
        self.assertTrue(all(row["status"] == "failed" for row in diagnostics))
        self.assertTrue(all(row["convergence_flag"] == 1 for row in diagnostics))
        self.assertTrue(all(row["iterations"] == 7 for row in diagnostics))
        self.assertTrue(forecasts.isna().all())


class Phase1KupiecTests(unittest.TestCase):
    def test_kupiec_handles_empty_and_degenerate_violation_samples(self):
        lr_empty, p_empty = phase1.kupiec(pd.Series(dtype=bool))
        self.assertTrue(np.isnan(lr_empty))
        self.assertTrue(np.isnan(p_empty))

        for violations in (pd.Series(np.zeros(100, dtype=bool)), pd.Series(np.ones(100, dtype=bool))):
            lr, p_value = phase1.kupiec(violations)
            self.assertTrue(np.isfinite(lr))
            self.assertGreaterEqual(lr, 0.0)
            self.assertGreaterEqual(p_value, 0.0)
            self.assertLessEqual(p_value, 1.0)

    def test_empty_forecast_is_reported_unavailable(self):
        returns = pd.Series([0.0, 1.0, -1.0], index=pd.date_range("2020-01-01", periods=3))
        forecast = pd.Series(np.nan, index=returns.index)
        row = phase1.avaliar("TEST", returns, {"GJR-GARCH-t": forecast})[0]
        self.assertEqual(row["n_obs"], 0)
        self.assertEqual(row["veredito"], "indisponível")
        self.assertTrue(np.isnan(row["p_valor_kupiec"]))


if __name__ == "__main__":
    unittest.main()
