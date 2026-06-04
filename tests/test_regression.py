"""
Unit tests for the regression detection engine.

Covers:
  - ``_z_score`` — basic computation, edge cases
  - ``_cusum`` — stable series, shifted series, no change points
  - ``RegressionAlert`` — defaults, serialization roundtrip
  - ``detect_regression`` — degradation, improvement, stable, insufficient data,
    z-score method, custom thresholds
  - ``detect_all`` — discovers model/metric pairs, sorts by severity
  - ``AlertStore`` — store, list with filters, stats, empty store
"""

import math
import os
import tempfile
import unittest
from datetime import datetime, timezone

from core.regression import (
    RegressionAlert,
    _z_score,
    _cusum,
    detect_regression,
    detect_all,
    AlertStore,
    get_alert_store,
)

# ═════════════════════════════════════════════════════════════════════
#  _Z_SCORE
# ═════════════════════════════════════════════════════════════════════


class TestZScore(unittest.TestCase):
    """Tests for the internal _z_score function."""

    def test_basic_z_scores(self):
        """Z-scores should center and scale normally."""
        values = [10.0, 12.0, 8.0, 11.0, 9.0]
        scores = _z_score(values)
        self.assertEqual(len(scores), 5)
        # Mean should be ~0 with unit variance (n-1)
        self.assertAlmostEqual(sum(scores), 0.0, places=10)

    def test_single_value(self):
        """A single value should return [0.0]."""
        scores = _z_score([42.0])
        self.assertEqual(scores, [0.0])

    def test_two_values(self):
        """Two identical values should produce [0.0, 0.0]."""
        scores = _z_score([5.0, 5.0])
        self.assertEqual(scores, [0.0, 0.0])

    def test_two_different_values(self):
        """Two different values should produce equal-magnitude opposite z-scores."""
        scores = _z_score([0.0, 10.0])
        self.assertEqual(len(scores), 2)
        self.assertAlmostEqual(scores[0], -scores[1], places=10)

    def test_constant_values(self):
        """All-identical values should produce all zeros (std=0→1e-10→~0)."""
        scores = _z_score([3.0, 3.0, 3.0, 3.0])
        for s in scores:
            self.assertAlmostEqual(s, 0.0, places=10)

    def test_empty_sequence(self):
        """Empty sequence should return empty list."""
        scores = _z_score([])
        self.assertEqual(scores, [])


# ═════════════════════════════════════════════════════════════════════
#  _CUSUM
# ═════════════════════════════════════════════════════════════════════


class TestCUSUM(unittest.TestCase):
    """Tests for the internal _cusum change-point detection function."""

    def test_stable_series_no_change_points(self):
        """A stable series with small noise should produce no change points."""
        values = [100.0] * 20
        cumsum, cps = _cusum(values, threshold=5.0)
        self.assertEqual(len(cumsum), 20)
        self.assertEqual(cps, [], "Stable series should have no change points")

    def test_slight_noise_no_change_points(self):
        """A series with minor noise should not trigger change points."""
        values = [100.0 + math.sin(i) * 2.0 for i in range(20)]
        cumsum, cps = _cusum(values, threshold=5.0)
        self.assertEqual(cps, [], "Slight noise should not trigger change points")

    def test_sharp_drop_detects_change_point(self):
        """A sharp sustained drop should produce a change point."""
        # 10 values at 100, then 10 values at 50
        values = [100.0] * 10 + [50.0] * 10
        cumsum, cps = _cusum(values, threshold=5.0)
        self.assertGreater(len(cps), 0, "Sharp drop should produce a change point")
        # The change point should be near index 10 (where the drop occurs)
        self.assertGreaterEqual(cps[0], 5, "Change point should be near or after the shift")

    def test_sharp_rise_detects_change_point(self):
        """A sharp sustained rise should produce a change point."""
        values = [50.0] * 10 + [100.0] * 10
        cumsum, cps = _cusum(values, threshold=5.0)
        self.assertGreater(len(cps), 0, "Sharp rise should produce a change point")

    def test_cumsum_length_matches_input(self):
        """Cumulative sum output length should match input length."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        cumsum, cps = _cusum(values)
        self.assertEqual(len(cumsum), len(values))

    def test_lower_threshold_more_sensitive(self):
        """Lower threshold should make CUSUM more sensitive."""
        values = [100.0] * 10 + [90.0] * 10  # 10% drop
        _, cps_strict = _cusum(values, threshold=3.0)
        _, cps_loose = _cusum(values, threshold=10.0)
        self.assertGreaterEqual(len(cps_strict), len(cps_loose),
                                "Lower threshold should be more sensitive")

    def test_single_value_no_change_points(self):
        """Single value should produce no change points."""
        cumsum, cps = _cusum([42.0])
        self.assertEqual(cps, [])
        self.assertEqual(cumsum, [0.0])

    def test_two_identical_values_no_change_points(self):
        """Two identical values should produce no change points."""
        cumsum, cps = _cusum([10.0, 10.0])
        self.assertEqual(cps, [])

    def test_cumsum_starts_at_zero(self):
        """Cumulative sum should start at 0."""
        cumsum, cps = _cusum([5.0, 10.0, 15.0])
        self.assertEqual(cumsum[0], 0.0)


# ═════════════════════════════════════════════════════════════════════
#  REGRESSION ALERT DATACLASS
# ═════════════════════════════════════════════════════════════════════


class TestRegressionAlert(unittest.TestCase):
    """Tests for the RegressionAlert dataclass."""

    def test_default_severity_and_direction(self):
        """Alert should default to warning severity and degradation direction."""
        alert = RegressionAlert(model="qwen", metric="tokens_per_second")
        self.assertEqual(alert.severity, "warning")
        self.assertEqual(alert.direction, "degradation")

    def test_default_timestamp_set_on_init(self):
        """Alert should auto-generate timestamp on creation."""
        alert = RegressionAlert(model="qwen", metric="tokens_per_second")
        self.assertTrue(len(alert.timestamp) > 0)
        # Should be ISO 8601 format
        self.assertIn("T", alert.timestamp)

    def test_custom_timestamp_preserved(self):
        """Custom timestamp should not be overridden."""
        ts = "2026-06-04T12:00:00+00:00"
        alert = RegressionAlert(model="qwen", metric="tokens_per_second", timestamp=ts)
        self.assertEqual(alert.timestamp, ts)

    def test_to_dict_roundtrip(self):
        """to_dict() followed by from_dict() should produce an identical alert."""
        alert = RegressionAlert(
            model="qwen-3.5-9b",
            metric="tokens_per_second",
            severity="critical",
            direction="degradation",
            confidence=0.95,
            change_magnitude=27.7,
            previous_avg=102.3,
            current_value=74.6,
            baseline_std=4.2,
            z_score=-12.8,
            window_size=20,
            run_id="run_abc",
        )
        reconstructed = RegressionAlert.from_dict(alert.to_dict())
        self.assertEqual(reconstructed.model, alert.model)
        self.assertEqual(reconstructed.metric, alert.metric)
        self.assertEqual(reconstructed.severity, alert.severity)
        self.assertEqual(reconstructed.direction, alert.direction)
        self.assertEqual(reconstructed.confidence, alert.confidence)
        self.assertEqual(reconstructed.change_magnitude, alert.change_magnitude)
        self.assertEqual(reconstructed.run_id, alert.run_id)
        self.assertEqual(reconstructed.window_size, alert.window_size)

    def test_to_dict_contains_all_keys(self):
        """to_dict() should contain all dataclass fields."""
        alert = RegressionAlert(model="m", metric="score")
        d = alert.to_dict()
        expected_keys = {
            "model", "metric", "severity", "direction", "confidence",
            "change_magnitude", "previous_avg", "current_value",
            "baseline_std", "z_score", "window_size", "timestamp", "run_id",
        }
        self.assertSetEqual(set(d.keys()), expected_keys)

    def test_from_dict_with_minimal_data(self):
        """from_dict should handle minimal data with defaults."""
        d = {"model": "test", "metric": "test_metric"}
        alert = RegressionAlert.from_dict(d)
        self.assertEqual(alert.model, "test")
        self.assertEqual(alert.metric, "test_metric")
        self.assertEqual(alert.severity, "warning")  # default
        self.assertEqual(alert.direction, "degradation")  # default


# ═════════════════════════════════════════════════════════════════════
#  DETECT_REGRESSION
# ═════════════════════════════════════════════════════════════════════


class TestDetectRegression(unittest.TestCase):
    """Tests for detect_regression — requires a MetricsStore."""

    def setUp(self):
        from core.metrics_store import MetricsStore

        # Create a temporary SQLite DB for each test
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = MetricsStore(self.db_path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _record_values(self, values, model="test-model", metric="tokens_per_second"):
        """Helper: record a time-ordered list of values."""
        for val in values:
            self.store.record(metric, val, model=model, unit="tokens/s")

    def test_detects_degradation(self):
        """A sharp drop in values should be detected as a degradation."""
        # 15 stable values around 100, then 5 values around 70
        baseline = [100.0 + math.sin(i) * 3.0 for i in range(15)]
        degraded = [70.0 + math.sin(i) * 3.0 for i in range(5)]
        self._record_values(baseline + degraded)

        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20)
        self.assertGreater(len(alerts), 0, "Degradation should be detected")
        alert = alerts[0]
        self.assertEqual(alert.direction, "degradation")
        self.assertIn(alert.severity, ("warning", "critical"))
        self.assertGreater(alert.change_magnitude, 15.0,
                           "Change magnitude should reflect ~28% drop")
        self.assertIsNotNone(alert.z_score)
        self.assertIsNotNone(alert.previous_avg)
        self.assertIsNotNone(alert.current_value)

    def test_detects_improvement(self):
        """A sharp rise in values should be detected as an improvement."""
        baseline = [50.0 + math.sin(i) * 2.0 for i in range(15)]
        improved = [95.0 + math.sin(i) * 2.0 for i in range(5)]
        self._record_values(baseline + improved)

        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20)
        self.assertGreater(len(alerts), 0, "Improvement should be detected")
        alert = alerts[0]
        self.assertEqual(alert.direction, "improvement")

    def test_stable_series_no_alert(self):
        """A stable series with small noise should produce no alerts."""
        values = [100.0 + math.sin(i) * 2.0 for i in range(20)]
        self._record_values(values)
        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20)
        self.assertEqual(len(alerts), 0, "Stable series should not trigger alerts")

    def test_insufficient_data_returns_empty(self):
        """Fewer than min_samples data points should return empty list."""
        self._record_values([100.0, 101.0, 102.0])  # Only 3 values
        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=10, min_samples=10)
        self.assertEqual(len(alerts), 0, "Insufficient data should return empty list")

    def test_insufficient_data_min_samples_default(self):
        """Below the default min_samples (5) should return empty."""
        self._record_values([100.0, 101.0, 102.0])
        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=10)
        self.assertEqual(len(alerts), 0)

    def test_zscore_method_detects_regression(self):
        """Using method='zscore' should still detect a clear regression."""
        baseline = [100.0] * 15
        degraded = [65.0] * 5
        self._record_values(baseline + degraded)

        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20,
                                   method="zscore")
        self.assertGreater(len(alerts), 0, "Z-score method should detect degradation")
        alert = alerts[0]
        self.assertGreater(alert.change_magnitude, 25.0)

    def test_cusum_method_detects_regression(self):
        """Using method='cusum' should detect a clear regression."""
        baseline = [100.0] * 15
        degraded = [60.0] * 5
        self._record_values(baseline + degraded)

        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20,
                                   method="cusum")
        self.assertGreater(len(alerts), 0, "CUSUM method should detect degradation")

    def test_high_threshold_reduces_false_positives(self):
        """A very high z-threshold should reduce detection of marginal shifts."""
        values = [100.0] * 10 + [95.0] * 10  # Only 5% drop
        self._record_values(values)

        alerts_loose = detect_regression(self.store, model="test-model",
                                         metric="tokens_per_second",
                                         window=20, z_threshold=1.0)
        alerts_strict = detect_regression(self.store, model="test-model",
                                          metric="tokens_per_second",
                                          window=20, z_threshold=5.0)
        self.assertGreaterEqual(len(alerts_loose), len(alerts_strict),
                                "Higher threshold should reduce detection rate")

    def test_different_model_not_detected(self):
        """A regression in one model should not trigger for another model."""
        self._record_values([100.0] * 15 + [50.0] * 5, model="model-a")
        self._record_values([100.0] * 20, model="model-b")

        alerts_a = detect_regression(self.store, model="model-a",
                                     metric="tokens_per_second", window=20)
        alerts_b = detect_regression(self.store, model="model-b",
                                     metric="tokens_per_second", window=20)
        self.assertGreater(len(alerts_a), 0, "model-a should have regression")
        self.assertEqual(len(alerts_b), 0, "model-b should have no regression")

    def test_alert_includes_model_and_metric(self):
        """Alert should carry the correct model and metric names."""
        self._record_values([100.0] * 15 + [60.0] * 5)
        alerts = detect_regression(self.store, model="test-model",
                                   metric="tokens_per_second", window=20)
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].model, "test-model")
        self.assertEqual(alerts[0].metric, "tokens_per_second")

    def test_raises_type_error_for_wrong_store_type(self):
        """Passing a non-MetricsStore should raise TypeError."""
        with self.assertRaises(TypeError):
            detect_regression("not_a_store", model="m", metric="m")


# ═════════════════════════════════════════════════════════════════════
#  DETECT_ALL
# ═════════════════════════════════════════════════════════════════════


class TestDetectAll(unittest.TestCase):
    """Tests for detect_all — bulk regression detection across model/metric pairs."""

    def setUp(self):
        from core.metrics_store import MetricsStore

        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = MetricsStore(self.db_path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _record(self, values, model, metric="tokens_per_second"):
        for val in values:
            self.store.record(metric, val, model=model)

    def test_detects_across_multiple_models(self):
        """detect_all should find regressions across multiple models."""
        # model-a: stable
        self._record([100.0] * 20, model="model-a")
        # model-b: degraded
        self._record([100.0] * 15 + [60.0] * 5, model="model-b")

        alerts = detect_all(self.store, window=20)
        # Should find at least 1 alert (model-b)
        self.assertGreater(len(alerts), 0)
        # All alerts should be for model-b
        for a in alerts:
            self.assertEqual(a.model, "model-b")

    def test_detects_across_multiple_metrics(self):
        """detect_all should find regressions across multiple metrics."""
        self._record([100.0] * 15 + [50.0] * 5, model="test-model", metric="tokens_per_second")
        self._record([200.0] * 20, model="test-model", metric="ttft_ms")

        alerts = detect_all(self.store, window=20)
        alert_metrics = {a.metric for a in alerts}
        self.assertIn("tokens_per_second", alert_metrics)
        self.assertNotIn("ttft_ms", alert_metrics)

    def test_empty_store_returns_empty(self):
        """An empty MetricsStore should return no alerts."""
        alerts = detect_all(self.store)
        self.assertEqual(alerts, [])

    def test_sorts_by_severity_then_confidence(self):
        """Alerts should be sorted critical first, then by confidence descending."""
        self._record([100.0] * 15 + [40.0] * 5, model="m", metric="big_drop")  # critical
        self._record([100.0] * 15 + [82.0] * 5, model="m", metric="small_drop")  # warning

        alerts = detect_all(self.store, window=20)
        if len(alerts) >= 2:
            self.assertEqual(alerts[0].severity, "critical",
                             "Critical alerts should come first")

    def test_specified_metrics_only(self):
        """detect_all should only check explicitly specified metrics."""
        self._record([100.0] * 15 + [50.0] * 5, model="m", metric="tokens_per_second")
        self._record([100.0] * 15 + [50.0] * 5, model="m", metric="ttft_ms")
        self._record([100.0] * 20, model="m", metric="memory_mb")

        alerts = detect_all(self.store, metrics=["tokens_per_second", "ttft_ms"],
                            window=20)  # must match data size for clean split
        alert_metrics = {a.metric for a in alerts}
        self.assertIn("tokens_per_second", alert_metrics)
        self.assertIn("ttft_ms", alert_metrics)
        self.assertNotIn("memory_mb", alert_metrics)

    def test_specified_models_only(self):
        """detect_all should only check explicitly specified models."""
        self._record([100.0] * 15 + [50.0] * 5, model="model-a")
        self._record([100.0] * 15 + [50.0] * 5, model="model-b")

        alerts = detect_all(self.store, models=["model-a"], window=20)
        for a in alerts:
            self.assertEqual(a.model, "model-a")

    def test_raises_type_error_for_wrong_store_type(self):
        """Passing a non-MetricsStore should raise TypeError."""
        with self.assertRaises(TypeError):
            detect_all("not_a_store")


# ═════════════════════════════════════════════════════════════════════
#  ALERT STORE
# ═════════════════════════════════════════════════════════════════════


class TestAlertStore(unittest.TestCase):
    """Tests for AlertStore — SQLite persistence for regression alerts."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = AlertStore(self.db_path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _make_alert(self, model="test-model", metric="tokens_per_second",
                    severity="warning", run_id="", **kwargs):
        return RegressionAlert(
            model=model,
            metric=metric,
            severity=severity,
            run_id=run_id,
            **kwargs,
        )

    def test_store_alert_returns_row_id(self):
        """Storing an alert should return a positive integer row ID."""
        alert = self._make_alert()
        row_id = self.store.store(alert)
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

    def test_list_alerts_returns_stored_alert(self):
        """Stored alerts should be retrievable via list_alerts."""
        alert = self._make_alert()
        self.store.store(alert)

        alerts = self.store.list_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].model, "test-model")
        self.assertEqual(alerts[0].metric, "tokens_per_second")

    def test_list_alerts_empty_store(self):
        """An empty AlertStore should return an empty list."""
        alerts = self.store.list_alerts()
        self.assertEqual(alerts, [])

    def test_filter_by_model(self):
        """list_alerts should filter by model name."""
        self.store.store(self._make_alert(model="model-a"))
        self.store.store(self._make_alert(model="model-b"))

        alerts = self.store.list_alerts(model="model-a")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].model, "model-a")

    def test_filter_by_metric(self):
        """list_alerts should filter by metric name."""
        self.store.store(self._make_alert(metric="tokens_per_second"))
        self.store.store(self._make_alert(metric="ttft_ms"))

        alerts = self.store.list_alerts(metric="ttft_ms")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].metric, "ttft_ms")

    def test_filter_by_severity(self):
        """list_alerts should filter by severity level."""
        self.store.store(self._make_alert(severity="info"))
        self.store.store(self._make_alert(severity="warning"))
        self.store.store(self._make_alert(severity="critical"))

        criticals = self.store.list_alerts(severity="critical")
        self.assertEqual(len(criticals), 1)
        self.assertEqual(criticals[0].severity, "critical")

        warnings = self.store.list_alerts(severity="warning")
        self.assertEqual(len(warnings), 1)

        infos = self.store.list_alerts(severity="info")
        self.assertEqual(len(infos), 1)

    def test_limit(self):
        """list_alerts should respect the limit parameter."""
        for i in range(10):
            self.store.store(self._make_alert(model=f"model-{i}"))

        limited = self.store.list_alerts(limit=3)
        self.assertLessEqual(len(limited), 3)

    def test_offset(self):
        """list_alerts should support pagination via offset."""
        for i in range(5):
            self.store.store(self._make_alert(model=f"model-{i}"))

        page_1 = self.store.list_alerts(limit=2, offset=0)
        page_2 = self.store.list_alerts(limit=2, offset=2)
        self.assertEqual(len(page_1), 2)
        self.assertEqual(len(page_2), 2)
        # Different models due to chronological order (newest first)
        page_1_models = {a.model for a in page_1}
        page_2_models = {a.model for a in page_2}
        self.assertNotEqual(page_1_models, page_2_models)

    def test_stats_empty_store(self):
        """Stats on an empty store should return zeros."""
        stats = self.store.stats()
        self.assertEqual(stats.get("total", 0), 0)
        self.assertEqual(stats.get("critical", 0), 0)
        self.assertEqual(stats.get("warning", 0), 0)
        self.assertEqual(stats.get("info", 0), 0)

    def test_stats_counts_severities(self):
        """Stats should correctly count alerts by severity."""
        self.store.store(self._make_alert(severity="critical"))
        self.store.store(self._make_alert(severity="critical"))
        self.store.store(self._make_alert(severity="warning"))
        self.store.store(self._make_alert(severity="info"))

        stats = self.store.stats()
        self.assertEqual(stats.get("total"), 4)
        self.assertEqual(stats.get("critical"), 2)
        self.assertEqual(stats.get("warning"), 1)
        self.assertEqual(stats.get("info"), 1)

    def test_stats_counts_models_and_metrics(self):
        """Stats should count distinct models and metrics."""
        self.store.store(self._make_alert(model="m1", metric="tokens_per_second"))
        self.store.store(self._make_alert(model="m1", metric="ttft_ms"))
        self.store.store(self._make_alert(model="m2", metric="tokens_per_second"))

        stats = self.store.stats()
        self.assertEqual(stats.get("total"), 3)
        self.assertEqual(stats.get("model_count"), 2)
        self.assertEqual(stats.get("metric_count"), 2)

    def test_stats_has_latest_alert_timestamp(self):
        """Stats should report the latest alert timestamp."""
        self.store.store(self._make_alert())
        stats = self.store.stats()
        self.assertIsNotNone(stats.get("latest_alert"))
        self.assertGreater(len(stats.get("latest_alert", "")), 0)

    def test_filtered_list_with_run_id(self):
        """list_alerts should preserve run_id when filtering."""
        alert = self._make_alert(run_id="run_abc")
        self.store.store(alert)
        alerts = self.store.list_alerts(run_id="run_abc")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].run_id, "run_abc")

    def test_multiple_list_calls(self):
        """Multiple list_alerts calls should work (connection stays open)."""
        self.store.store(self._make_alert(model="a"))
        self.store.store(self._make_alert(model="b"))

        a_alerts = self.store.list_alerts(model="a")
        b_alerts = self.store.list_alerts(model="b")
        all_alerts = self.store.list_alerts()

        self.assertEqual(len(a_alerts), 1)
        self.assertEqual(len(b_alerts), 1)
        self.assertEqual(len(all_alerts), 2)


# ═════════════════════════════════════════════════════════════════════
#  GET_ALERT_STORE
# ═════════════════════════════════════════════════════════════════════


class TestGetAlertStore(unittest.TestCase):
    """Tests for the get_alert_store convenience function."""

    def setUp(self):
        # Reset the global singleton between tests
        import core.regression
        core.regression._default_alert_store = None

    def test_returns_alert_store_instance(self):
        """get_alert_store should return an AlertStore instance."""
        store = get_alert_store()
        self.assertIsInstance(store, AlertStore)

    def test_returns_same_instance_for_default_path(self):
        """Multiple calls with default path should return the same instance."""
        store1 = get_alert_store()
        store2 = get_alert_store()
        self.assertIs(store1, store2)

    def test_different_paths_different_instances(self):
        """Different paths should create different instances."""
        store1 = get_alert_store("/tmp/test_alerts_1.db")
        store2 = get_alert_store("/tmp/test_alerts_2.db")
        self.assertIsNot(store1, store2)

    def tearDown(self):
        import core.regression
        core.regression._default_alert_store = None
        for path in ["/tmp/test_alerts_1.db", "/tmp/test_alerts_2.db"]:
            if os.path.exists(path):
                os.remove(path)


# ═════════════════════════════════════════════════════════════════════
#  EDGE CASES
# ═════════════════════════════════════════════════════════════════════


class TestRegressionEdgeCases(unittest.TestCase):
    """Additional edge cases for regression detection."""

    def setUp(self):
        from core.metrics_store import MetricsStore

        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = MetricsStore(self.db_path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_single_metric_no_regression(self):
        """A single metric with a small variance should not alarm."""
        for i in range(20):
            self.store.record("latency", round(100.0 + math.sin(i) * 5.0, 2),
                              model="m", unit="ms")
        alerts = detect_regression(self.store, model="m", metric="latency", window=20)
        self.assertEqual(len(alerts), 0)

    def test_gradual_degradation_still_detected(self):
        """A gradual linear degradation should still be detected."""
        values = [100.0 - i * 2.0 for i in range(20)]  # 100, 98, 96, ..., 62
        for v in values:
            self.store.record("score", v, model="m")
        alerts = detect_regression(self.store, model="m", metric="score", window=20)
        self.assertGreater(len(alerts), 0, "Gradual degradation should be detected")

    def test_recovery_not_detected_as_degradation(self):
        """A recovery (low then high) should be detected as improvement, not degradation."""
        values = [50.0] * 10 + [95.0] * 10
        for v in values:
            self.store.record("score", v, model="m")
        alerts = detect_regression(self.store, model="m", metric="score", window=20)
        if alerts:
            self.assertEqual(alerts[0].direction, "improvement")

    def test_no_false_positive_on_periodic_pattern(self):
        """A periodic pattern (sinusoidal) should not reguarly trigger alerts."""
        import math
        values = [100.0 + 15.0 * math.sin(i * 0.5) for i in range(40)]
        for v in values:
            self.store.record("score", v, model="m")
        alerts = detect_regression(self.store, model="m", metric="score", window=20)
        # Should not reliably trigger — periodic patterns are not sustained shifts
        self.assertEqual(len(alerts), 0,
                         "Periodic pattern should not trigger alerts")

    def test_zero_baseline_does_not_crash(self):
        """A baseline of zero (or near-zero) should not cause division errors."""
        self.store.record("score", 0.0, model="m")
        self.store.record("score", 0.0, model="m")
        self.store.record("score", 0.0, model="m")
        # Should not raise ZeroDivisionError
        try:
            alerts = detect_regression(self.store, model="m", metric="score", window=3, min_samples=3)
        except ZeroDivisionError:
            self.fail("detect_regression raised ZeroDivisionError on zero baseline")
        # May or may not detect a regression — just shouldn't crash


if __name__ == "__main__":
    unittest.main()
