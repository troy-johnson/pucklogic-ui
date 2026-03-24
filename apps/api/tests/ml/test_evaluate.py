from __future__ import annotations

import pytest

from ml.evaluate import MetricsResult, compute_metrics


class TestComputeMetrics:
    def test_perfect_classifier(self):
        y_true = [1, 1, 0, 0]
        y_proba = [0.9, 0.8, 0.1, 0.2]
        result = compute_metrics(y_true, y_proba)
        assert result.auc_roc == pytest.approx(1.0, abs=1e-6)

    def test_random_classifier_auc_near_half(self):
        y_true = [1, 0, 1, 0]
        y_proba = [0.5, 0.5, 0.5, 0.5]
        result = compute_metrics(y_true, y_proba)
        assert 0.0 <= result.auc_roc <= 1.0

    def test_precision_recall_at_50_all_positives(self):
        y_true = [1] * 50 + [0] * 50
        y_proba = [0.9] * 50 + [0.1] * 50
        result = compute_metrics(y_true, y_proba)
        # Top-50 are all true positives → precision=1.0, recall=1.0
        assert result.precision_at_50 == pytest.approx(1.0, abs=1e-6)
        assert result.recall_at_50 == pytest.approx(1.0, abs=1e-6)

    def test_precision_recall_at_50_no_positives_in_top(self):
        y_true = [0] * 50 + [1] * 50
        y_proba = [0.9] * 50 + [0.1] * 50  # model ranks negatives first
        result = compute_metrics(y_true, y_proba)
        assert result.precision_at_50 == pytest.approx(0.0, abs=1e-6)
        assert result.recall_at_50 == pytest.approx(0.0, abs=1e-6)

    def test_returns_metrics_result_type(self):
        result = compute_metrics([1, 0], [0.8, 0.2])
        assert isinstance(result, MetricsResult)

    def test_precision_at_50_fewer_than_50_samples(self):
        y_true = [1, 0, 1]
        y_proba = [0.9, 0.5, 0.7]
        result = compute_metrics(y_true, y_proba)
        # Falls back to all samples when N < 50
        assert 0.0 <= result.precision_at_50 <= 1.0
        assert 0.0 <= result.recall_at_50 <= 1.0

    def test_all_negative_labels_returns_random_baseline(self):
        """Single-class fold (all 0s) must not raise — returns auc_roc=0.5."""
        y_true = [0, 0, 0, 0, 0]
        y_proba = [0.9, 0.6, 0.4, 0.2, 0.1]
        result = compute_metrics(y_true, y_proba)
        assert result.auc_roc == pytest.approx(0.5, abs=1e-6)
        assert result.precision_at_50 == pytest.approx(0.0, abs=1e-6)

    def test_all_positive_labels_returns_random_baseline(self):
        """Single-class fold (all 1s) must not raise — returns auc_roc=0.5."""
        y_true = [1, 1, 1, 1, 1]
        y_proba = [0.9, 0.6, 0.4, 0.2, 0.1]
        result = compute_metrics(y_true, y_proba)
        assert result.auc_roc == pytest.approx(0.5, abs=1e-6)
        assert result.recall_at_50 == pytest.approx(1.0, abs=1e-6)
