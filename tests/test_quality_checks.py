import pytest

from quality.checks import CheckResult, QualityGateError, gate, rate_check


def test_rate_below_warning_passes():
    assert rate_check("r", "orders", 0, 100, 0.01, 0.2).status == "pass"


def test_rate_between_thresholds_warns_without_failing():
    result = rate_check("r", "orders", 5, 100, 0.01, 0.2)
    assert (result.status, result.severity) == ("warn", "warning")
    gate([result])  # a warning never stops the pipeline


def test_rate_above_critical_fails():
    result = rate_check("r", "orders", 30, 100, 0.01, 0.2)
    assert (result.status, result.severity) == ("fail", "critical")


def test_zero_rows_is_critical():
    assert rate_check("r", "orders", 0, 0, 0.01, 0.2).status == "fail"


def test_gate_raises_on_critical_failure():
    with pytest.raises(QualityGateError, match="source_file_loaded"):
        gate([CheckResult("source_file_loaded", "orders", "critical", "fail", details="file_missing")])
