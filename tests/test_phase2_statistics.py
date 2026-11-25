import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import phase2_risk_engine_v2 as phase2
import var_baseline as phase1
from b3_sessions import completed_sessions


class MultipleTestingTests(unittest.TestCase):
    def test_holm_adjustment_matches_step_down_values(self):
        raw = pd.Series([0.01, 0.04, 0.03, 0.002], name="p")
        adjusted = phase2.adjust_pvalues(raw, "holm")
        np.testing.assert_allclose(adjusted.to_numpy(), [0.03, 0.06, 0.06, 0.008])
        np.testing.assert_array_equal(raw.to_numpy(), [0.01, 0.04, 0.03, 0.002])

    def test_bh_adjustment_is_monotone_in_rank_and_preserves_nan(self):
        raw = pd.Series([0.01, np.nan, 0.04, 0.002], name="p")
        adjusted = phase2.adjust_pvalues(raw, "bh")
        np.testing.assert_allclose(adjusted.iloc[[0, 2, 3]], [0.015, 0.04, 0.006])
        self.assertTrue(np.isnan(adjusted.iloc[1]))

    def test_adjusted_columns_leave_original_pvalues_untouched(self):
        frame = pd.DataFrame({"kupiec_p_value": [0.01, 0.04]})
        result = phase2.add_adjusted_pvalues(frame, ["kupiec_p_value"], "holm")
        np.testing.assert_array_equal(result["kupiec_p_value"], [0.01, 0.04])
        np.testing.assert_allclose(result["kupiec_p_value_holm"], [0.02, 0.04])

    def test_pvalue_fora_do_intervalo_e_rejeitado(self):
        with self.assertRaises(ValueError):
            phase2.adjust_pvalues(pd.Series([1.2]), "bh")


class Phase2SampleTests(unittest.TestCase):
    def test_validacao_apos_transformacao_em_retornos(self):
        count = phase2.MIN_TOTAL_RETURNS + 1
        dates = completed_sessions("2010-01-01", pd.Timestamp("2017-01-01", tz="UTC"))[:count]
        prices = pd.Series(np.exp(np.arange(count) * 0.0001), index=dates, name="asset")
        returns = phase2._validate_return_sample(prices, "asset")
        self.assertEqual(len(returns), phase2.MIN_TOTAL_RETURNS)
        with self.assertRaisesRegex(RuntimeError, "Amostra insuficiente"):
            phase2._validate_return_sample(prices.iloc[:-1], "asset")

    def test_cache_curto_solicita_historico_completo(self):
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        dates = pd.date_range(end=today - pd.Timedelta(days=100), periods=100, freq="D")
        short_cache = pd.Series(np.exp(np.arange(100) * 0.0001), index=dates, name="PETR4")
        full_dates = completed_sessions("2010-01-01", pd.Timestamp.now(tz="UTC"))[-(phase2.MIN_TOTAL_RETURNS + 1):]
        full_history = pd.Series(np.exp(np.arange(len(full_dates)) * 0.0001), index=full_dates, name="PETR4")
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            short_cache.to_frame("Close").to_csv(data_dir / "PETR4.csv")
            with patch.object(phase2, "DATA_DIR", data_dir), patch.object(
                phase2, "_download_yahoo", return_value=full_history
            ) as downloader:
                prices = phase2.load_prices("PETR4", "PETR4.SA")
            downloader.assert_called_once_with("PETR4.SA", "PETR4", start_date=phase2.START_DATE)
            self.assertEqual(len(phase2.prices_to_returns(prices)), phase2.MIN_TOTAL_RETURNS)

    def test_normalizacao_deduplica_ordena_e_descarta_precos_invalidos(self):
        dates = pd.date_range("2020-01-01", periods=5, freq="D")
        values = pd.Series([5.0, 2.0, 0.0, 4.0, 3.0], index=[dates[4], dates[1], dates[2], dates[3], dates[1]])
        clean = phase2._normalise_price_series(values, "asset")
        self.assertTrue(clean.index.is_monotonic_increasing)
        self.assertFalse(clean.index.has_duplicates)
        self.assertTrue((clean > 0).all())
        self.assertEqual(len(clean), 3)
        self.assertEqual(clean.loc[dates[1]], 3.0)

    def test_normalizacao_rejeita_data_futura_e_data_invalida(self):
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        values = pd.Series([10.0, 11.0, 12.0], index=[today, today + pd.Timedelta(days=1), pd.NaT])
        clean = phase2._normalise_price_series(values, "asset")
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean.index[0], today)


class GarchForecastAlignmentTests(unittest.TestCase):
    def test_fixed_block_uses_window_prefix_and_starts_at_first_forecast(self):
        returns = pd.Series(np.arange(1.0, 9.0), index=pd.date_range("2020-01-01", periods=8))
        observed_inputs = []

        class FixedModel:
            def __init__(self, values):
                self.values = values
                self.conditional_volatility = pd.Series(np.arange(1.0, len(values) + 1))

        class Model:
            def __init__(self, values):
                observed_inputs.append(values.copy())

            def fix(self, params):
                return FixedModel(observed_inputs[-1])

        with patch.object(phase2, "WINDOW", 3), patch.object(phase2, "arch_model", side_effect=lambda values, **_: Model(values)):
            sigma = phase2._fixed_garch_block_sigma(returns, pd.Series(dtype=float), {}, 3, 5)

        # First output is conditional volatility at position WINDOW, aligned to
        # the first out-of-sample return; the window prefix plus two-day block is used.
        np.testing.assert_array_equal(sigma, [4.0, 5.0])
        self.assertEqual(observed_inputs[0].tolist(), [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_returns_after_forecast_block_do_not_enter_filtering(self):
        first = pd.Series(np.arange(1.0, 9.0), index=pd.date_range("2020-01-01", periods=8))
        changed_future = first.copy()
        changed_future.iloc[5:] = 1_000_000.0

        def run(series):
            class FixedModel:
                def __init__(self, size):
                    self.conditional_volatility = pd.Series(np.arange(1.0, size + 1))

            class Model:
                def __init__(self, values):
                    self.size = len(values)

                def fix(self, params):
                    return FixedModel(self.size)

            with patch.object(phase2, "WINDOW", 3), patch.object(phase2, "arch_model", side_effect=lambda values, **_: Model(values)):
                return phase2._fixed_garch_block_sigma(series, pd.Series(dtype=float), {}, 3, 5)

        np.testing.assert_array_equal(run(first), run(changed_future))

    def test_real_gjr_fit_matches_one_step_forecasts_in_both_phases(self):
        # Série sintética isolada. Os seis retornos finais ficam fora do ajuste.
        window = 500
        rng = np.random.default_rng(57421)
        shocks = rng.standard_t(7, size=window + 6) * np.sqrt(5 / 7)
        values = np.empty_like(shocks)
        variance = 1.0
        for i, shock in enumerate(shocks):
            values[i] = np.sqrt(variance) * shock
            variance = 0.04 + (0.06 + 0.11 * (values[i] < 0)) * values[i]**2 + 0.84 * variance
        dates = completed_sessions("2010-01-01", pd.Timestamp("2013-01-01", tz="UTC"))[:len(values)]
        returns = pd.Series(values, index=dates)
        spec = dict(mean="Zero", vol="GARCH", p=1, o=1, q=1, dist="t")
        fit = phase2.arch_model(returns.iloc[:window], **spec).fit(disp="off")
        self.assertEqual(fit.convergence_flag, 0)
        nu = fit.params["nu"]
        quantile = phase2.stats.t.ppf(phase2.ALPHA, nu) * np.sqrt((nu - 2) / nu)
        expected = []
        for t in range(window, len(returns)):
            # Cada referência enxerga apenas a série terminada no dia anterior.
            past = phase2.arch_model(returns.iloc[:t], **spec).fix(fit.params)
            h_next = past.forecast(horizon=1, reindex=False).variance.iloc[-1, 0]
            expected.append(quantile * np.sqrt(h_next))
        with patch.object(phase1, "JANELA", window), patch.object(phase2, "WINDOW", window):
            var1, diag1 = phase1.var_gjr_garch_t(returns, "fixture")
            forecasts, diag2 = phase2.gjr_garch_t_var_es(returns, "fixture")
        for result, diag in [(var1, diag1), (forecasts.var, diag2)]:
            self.assertEqual([row["status"] for row in diag], ["ok"])
            self.assertTrue(result.iloc[:window].isna().all())
            np.testing.assert_allclose(result.iloc[window:], expected, atol=1e-8, rtol=1e-8)

    def test_missing_convergence_flag_is_not_reported_as_success(self):
        returns = pd.Series(np.linspace(-1.0, 1.0, 6), index=pd.date_range("2020-01-01", periods=6))

        class FitResult:
            params = pd.Series({"nu": 8.0})
            loglikelihood = -10.0

        class Model:
            def fit(self, **kwargs):
                return FitResult()

        with patch.object(phase2, "WINDOW", 3), patch.object(phase2, "GARCH_REFIT_EVERY", 2), patch.object(
            phase2, "arch_model", side_effect=lambda *_args, **_kwargs: Model()
        ):
            forecasts, diagnostics = phase2.gjr_garch_t_var_es(returns, "TEST")

        self.assertEqual(diagnostics[0]["status"], "failed")
        self.assertTrue(np.isnan(diagnostics[0]["convergence_flag"]))
        self.assertIn("sem indicador de convergencia", diagnostics[0]["message"])
        self.assertTrue(forecasts.var.isna().all())


class QuantitativeFormulaTests(unittest.TestCase):
    def test_student_t_var_es_are_standardized_and_ordered(self):
        alpha = 0.01
        nu = 8.0
        var_z, es_z = phase2._standard_t_var_es(alpha, nu)
        scale = np.sqrt((nu - 2.0) / nu)
        q = phase2.stats.t.ppf(alpha, df=nu)
        expected_var = scale * q
        expected_es = scale * (-(nu + q * q) / (nu - 1.0) * phase2.stats.t.pdf(q, df=nu) / alpha)
        self.assertAlmostEqual(var_z, expected_var, places=12)
        self.assertAlmostEqual(es_z, expected_es, places=12)
        self.assertLess(es_z, var_z)

    def test_ewma_forecast_for_t_does_not_use_return_at_t(self):
        returns = pd.Series([1.0, -2.0, 0.5, -1.0, 3.0, 2.0])
        changed = returns.copy()
        changed.iloc[4] = -900.0
        with patch.object(phase2, "WINDOW", 3):
            original = phase2.ewma_var_es(returns)
            altered = phase2.ewma_var_es(changed)
        self.assertAlmostEqual(original.var.iloc[4], altered.var.iloc[4], places=12)
        self.assertAlmostEqual(original.es.iloc[4], altered.es.iloc[4], places=12)

    def test_portfolio_return_uses_simple_returns_before_log(self):
        dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
        prices = {
            "A": pd.Series([100.0, 110.0], index=dates),
            "B": pd.Series([100.0, 90.0], index=dates),
        }
        result = phase2.build_portfolio_log_returns(prices, {"A": 0.5, "B": 0.5})
        self.assertAlmostEqual(result.iloc[0], 0.0, places=12)

    def test_gap_breaks_pairs_and_conditional_coverage_uses_the_same_destinations(self):
        dates = pd.to_datetime(["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19",
                                "2026-11-23", "2026-11-24", "2026-11-25"])
        returns = pd.Series([-4, 0, -5, -4, -3, 0, 0], index=dates)
        var = pd.Series(-2.0, index=dates)
        es = pd.Series(-3.0, index=dates)
        # Em um cenário faltou a observação. No outro faltou a previsão.
        for missing_quote in (True, False):
            with self.subTest(missing_quote=missing_quote):
                if missing_quote:
                    r, v, e = (series.drop(dates[2]) for series in (returns, var, es))
                else:
                    r, v, e = returns, var.mask(var.index == dates[2]), es
                metrics = phase2.evaluate_forecasts("A", "teste", r, phase2.ForecastSet(v, e), min_obs=1)
                self.assertEqual(metrics["n_obs"], 6)
                self.assertEqual(metrics["violations"], 3)
                self.assertEqual(metrics["omitted_gap_transitions"], 1)
                self.assertEqual([metrics[k] for k in ("n00", "n01", "n10", "n11")], [1, 0, 2, 1])
                # Dia 19 para 23 é consecutivo: dia 20 é feriado e 21/22 são fim de semana.
                self.assertEqual(metrics["valid_transitions"], 4)
                alt = 2 * np.log(2 / 3) + np.log(1 / 3)
                null = 3 * np.log1p(-phase2.ALPHA) + np.log(phase2.ALPHA)
                self.assertAlmostEqual(metrics["conditional_coverage_lr"], 2 * (alt - null))
                self.assertAlmostEqual(metrics["kupiec_lr_uc"], phase2.kupiec_unconditional_coverage(
                    np.array([1, 0, 1, 1, 0, 0]))[0])

    def test_no_consecutive_sessions_has_no_independence_verdict(self):
        dates = pd.to_datetime(["2026-11-16", "2026-11-18", "2026-11-23"])
        returns = pd.Series([-4, 1, 0], index=dates)
        forecast = phase2.ForecastSet(pd.Series(-2, index=dates), pd.Series(-3, index=dates))
        metrics = phase2.evaluate_forecasts("A", "teste", returns, forecast, min_obs=1)
        self.assertEqual(metrics["valid_transitions"], 0)
        self.assertEqual(metrics["omitted_gap_transitions"], 2)
        self.assertTrue(np.isnan(metrics["christoffersen_p_value"]))
        self.assertEqual(metrics["conditional_coverage_result_5pct"], "indisponivel")
        self.assertEqual(metrics["independence_result_5pct"], "indisponivel")

    def test_one_state_records_counts_and_unavailable_pvalue(self):
        lr, p, counts = phase2.christoffersen_independence(np.array([0, 0, 0]))
        self.assertEqual(counts, {"n00": 2, "n01": 0, "n10": 0, "n11": 0})
        self.assertTrue(np.isnan(lr) and np.isnan(p))

    def test_christoffersen_transition_counts_are_correct(self):
        lr, p_value, counts = phase2.christoffersen_independence(np.array([0, 0, 1, 0, 0, 1, 0]))
        self.assertEqual(counts, {"n00": 2, "n01": 2, "n10": 2, "n11": 0})
        self.assertGreaterEqual(lr, 0.0)
        self.assertGreaterEqual(p_value, 0.0)
        self.assertLessEqual(p_value, 1.0)


if __name__ == "__main__":
    unittest.main()
