from engine.study_engine import StudyEngine


def test_study_snapshot_has_simulated_data_and_indicators():
    engine = StudyEngine()
    result = engine.snapshot("EURUSD", 60, 50)
    assert result["mode"] == "SIMULATED"
    assert len(result["candles"]) == 50
    assert result["candles"][-1]["high"] >= result["candles"][-1]["low"]
    assert set(result["indicators"]) == {"sma_9", "sma_21", "rsi_14"}


def test_study_engine_is_reproducible_for_same_inputs():
    engine = StudyEngine()
    assert engine.candles("EURUSD", 60, 20) == engine.candles("EURUSD", 60, 20)


def test_rsi_is_bounded_when_available():
    engine = StudyEngine()
    metrics = engine.indicators(engine.candles("EURUSD", 60, 40))
    assert 0 <= metrics["rsi_14"] <= 100
