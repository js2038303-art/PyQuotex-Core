"""Educational SMA-crossover backtesting on synthetic candles only."""
from __future__ import annotations

from typing import Any


def backtest_sma(candles: list[dict[str, Any]], fast: int = 9, slow: int = 21) -> dict[str, Any]:
    if fast < 2 or slow <= fast or slow > 200:
        raise ValueError("Use fast >= 2 and slow > fast (maximum 200).")
    closes = [float(c["close"]) for c in candles]
    if len(closes) < slow + 2:
        raise ValueError(f"At least {slow + 2} candles are required.")
    trades: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None
    previous_fast = previous_slow = None

    for i in range(slow, len(closes)):
        fast_now = sum(closes[i-fast+1:i+1]) / fast
        slow_now = sum(closes[i-slow+1:i+1]) / slow
        if previous_fast is not None and previous_slow is not None:
            direction = None
            if previous_fast <= previous_slow and fast_now > slow_now:
                direction = "LONG"
            elif previous_fast >= previous_slow and fast_now < slow_now:
                direction = "SHORT"
            if direction and position is not None:
                entry = position["entry"]
                exit_price = closes[i]
                pnl_pct = ((exit_price - entry) / entry * 100) * (1 if position["side"] == "LONG" else -1)
                trades.append({
                    "side": position["side"], "entry": round(entry, 6),
                    "exit": round(exit_price, 6), "entry_time": position["time"],
                    "exit_time": candles[i]["time"], "pnl_pct": round(pnl_pct, 4),
                    "result": "WIN" if pnl_pct > 0 else "LOSS" if pnl_pct < 0 else "FLAT",
                })
                position = None
            if direction and position is None:
                position = {"side": direction, "entry": closes[i], "time": candles[i]["time"]}
        previous_fast, previous_slow = fast_now, slow_now

    if position is not None:
        entry = position["entry"]
        exit_price = closes[-1]
        pnl_pct = ((exit_price - entry) / entry * 100) * (1 if position["side"] == "LONG" else -1)
        trades.append({
            "side": position["side"], "entry": round(entry, 6),
            "exit": round(exit_price, 6), "entry_time": position["time"],
            "exit_time": candles[-1]["time"], "pnl_pct": round(pnl_pct, 4),
            "result": "WIN" if pnl_pct > 0 else "LOSS" if pnl_pct < 0 else "FLAT",
            "open_at_end": True,
        })

    wins = sum(t["result"] == "WIN" for t in trades)
    losses = sum(t["result"] == "LOSS" for t in trades)
    total = round(sum(t["pnl_pct"] for t in trades), 4)
    return {
        "mode": "SIMULATED_BACKTEST", "strategy": "SMA_CROSSOVER",
        "fast_period": fast, "slow_period": slow, "candles_tested": len(candles),
        "trades": trades, "total_trades": len(trades), "wins": wins,
        "losses": losses, "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else 0.0,
        "total_return_pct_simple": total,
        "disclaimer": "Backtest educacional em candles sintéticos; não prevê resultados reais e não executa operações.",
    }
