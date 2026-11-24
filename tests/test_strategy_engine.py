import pytest

from engine.study_engine import StudyEngine
from engine.strategy_engine import backtest_sma


def test_sma_backtest_returns_metrics_and_disclaimer():
    candles = StudyEngine().candles("EURUSD", 60, 180)
    result = backtest_sma(candles, fast=5, slow=15)
    assert result["mode"] == "SIMULATED_BACKTEST"
    assert result["candles_tested"] == 180
    assert result["total_trades"] == len(result["trades"])
    assert 0 <= result["win_rate_pct"] <= 100
    assert "sintéticos" in result["disclaimer"]


def test_backtest_rejects_invalid_periods():
    with pytest.raises(ValueError):
        backtest_sma(StudyEngine().candles(limit=80), fast=21, slow=9)


def test_backtest_requires_enough_candles():
    with pytest.raises(ValueError):
        backtest_sma(StudyEngine().candles(limit=20), fast=9, slow=21)
