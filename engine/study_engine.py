"""Deterministic paper-market engine for learning and UI development.

This module does not connect to Quotex and never places orders.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class StudyEngine:
    def __init__(self) -> None:
        self.started_at = int(time.time())
        self._seed = 20261124

    def candles(self, asset: str = "EURUSD", period: int = 60, limit: int = 120) -> list[dict[str, Any]]:
        """Return reproducible synthetic candles, clearly marked as simulated."""
        rng = random.Random(f"{self._seed}:{asset}:{period}")
        now = int(time.time())
        end = now - (now % period)
        price = 1.085 if "EUR" in asset.upper() else 100.0
        rows: list[dict[str, Any]] = []
        for index in range(limit):
            stamp = end - (limit - index - 1) * period
            drift = math.sin(index / 8) * 0.00015
            change = rng.uniform(-0.0007, 0.0007) + drift
            opening = price
            closing = max(0.00001, opening + change)
            spread = rng.uniform(0.00005, 0.00035)
            rows.append(asdict(Candle(
                time=stamp,
                open=round(opening, 6),
                high=round(max(opening, closing) + spread, 6),
                low=round(max(0.00001, min(opening, closing) - spread), 6),
                close=round(closing, 6),
                volume=rng.randint(20, 500),
            )))
            price = closing
        return rows

    @staticmethod
    def indicators(rows: list[dict[str, Any]]) -> dict[str, Any]:
        closes = [float(row["close"]) for row in rows]
        if not closes:
            return {"sma_9": None, "sma_21": None, "rsi_14": None}
        def sma(period: int) -> float | None:
            return round(sum(closes[-period:]) / period, 6) if len(closes) >= period else None
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        recent = changes[-14:]
        gains = sum(max(value, 0) for value in recent) / 14 if len(recent) >= 14 else None
        losses = sum(max(-value, 0) for value in recent) / 14 if len(recent) >= 14 else None
        if gains is None or losses is None:
            rsi = None
        elif losses == 0:
            rsi = 100.0
        else:
            rsi = round(100 - (100 / (1 + gains / losses)), 2)
        return {"sma_9": sma(9), "sma_21": sma(21), "rsi_14": rsi}

    def snapshot(self, asset: str = "EURUSD", period: int = 60, limit: int = 120) -> dict[str, Any]:
        rows = self.candles(asset, period, limit)
        metrics = self.indicators(rows)
        signal = "NEUTRO"
        if metrics["sma_9"] is not None and metrics["sma_21"] is not None:
            if metrics["sma_9"] > metrics["sma_21"]:
                signal = "TENDÊNCIA DE ALTA"
            elif metrics["sma_9"] < metrics["sma_21"]:
                signal = "TENDÊNCIA DE BAIXA"
        return {
            "mode": "SIMULATED",
            "disclaimer": "Dados sintéticos para estudo; não representam cotações reais.",
            "asset": asset,
            "period": period,
            "candles": rows,
            "indicators": metrics,
            "signal": signal,
        }


study_engine = StudyEngine()
