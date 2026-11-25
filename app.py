"""PyQuotex-Core API: DEMO-only broker gateway."""
from __future__ import annotations
import asyncio
from collections import deque
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from engine.study_engine import study_engine
from engine.strategy_engine import backtest_sma
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = logging.getLogger("pyquotex.api")
try:
    from pyquotex.stable_api import Quotex
except Exception as exc:
    Quotex = None
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
else:
    _IMPORT_ERROR = None

_client: Any = None
_connected = False
_connect_error = ""
_signal_history: deque[dict[str, Any]] = deque(maxlen=100)
_connect_lock = asyncio.Lock()
BROKER_TIMEOUT = float(os.getenv("QUOTEX_CONNECT_TIMEOUT", "45"))

def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "https://pyquotex-core.hatchable.site")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

async def _close_client(client: Any) -> None:
    if client is None:
        return
    try:
        await asyncio.wait_for(client.close(), timeout=10)
    except Exception:
        log.exception("Could not close broker client cleanly")

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    global _client, _connected
    async with _connect_lock:
        client, _client = _client, None
        _connected = False
        await _close_client(client)

app = FastAPI(title="PyQuotex-Core API", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

class ConnectRequest(BaseModel):
    demo: bool = True

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/study/snapshot")
async def study_snapshot(
    asset: str = Query(default="EURUSD", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$"),
    period: int = Query(default=60, ge=1, le=86400),
    limit: int = Query(default=120, ge=20, le=500),
):
    """Return synthetic market data for study; this endpoint never contacts the broker."""
    result = study_engine.snapshot(asset=asset, period=period, limit=limit)
    _signal_history.appendleft({
        "time": int(time.time()), "asset": asset, "period": period,
        "signal": result["signal"], "indicators": result["indicators"],
        "mode": "SIMULATED",
    })
    return result


@app.get("/api/study/signals")
async def study_signals(limit: int = Query(default=20, ge=1, le=100)):
    """Return recent in-memory study signals; history resets when the service restarts."""
    return {"mode": "SIMULATED", "signals": list(_signal_history)[:limit]}


@app.get("/api/study/backtest")
async def study_backtest(
    asset: str = Query(default="EURUSD", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$"),
    period: int = Query(default=60, ge=1, le=86400),
    limit: int = Query(default=300, ge=30, le=500),
    fast: int = Query(default=9, ge=2, le=100),
    slow: int = Query(default=21, ge=3, le=200),
):
    """Run an educational SMA crossover backtest on synthetic candles."""
    if fast >= slow:
        raise HTTPException(status_code=422, detail="O período rápido precisa ser menor que o lento.")
    candles_data = study_engine.candles(asset=asset, period=period, limit=limit)
    try:
        result = backtest_sma(candles_data, fast=fast, slow=slow)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result.update({"asset": asset, "period": period})
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "package_loaded": Quotex is not None,
            "connected": _connected, "account_mode": "PRACTICE",
            "trading_enabled": False, "import_error": _IMPORT_ERROR}

_otp_event: asyncio.Event | None = None
_otp_code: str | None = None
_otp_required = False
_otp_message = ""
_connecting = False
_connect_task: asyncio.Task | None = None

async def _request_otp(message: str) -> str:
    """Pause broker authentication until the browser submits its one-time PIN."""
    global _otp_event, _otp_code, _otp_required, _otp_message
    _otp_event = asyncio.Event()
    _otp_code = None
    _otp_message = (message or "Digite o código enviado pela Quotex.").strip()
    _otp_required = True
    try:
        await asyncio.wait_for(_otp_event.wait(), timeout=180)
        if not _otp_code:
            raise RuntimeError("Código PIN não recebido.")
        return _otp_code
    finally:
        _otp_required = False
        _otp_message = ""
        _otp_event = None
        _otp_code = None

async def _connect_worker() -> None:
    global _client, _connected, _connecting, _connect_error
    candidate = None
    try:
        email, password = os.getenv("QUOTEX_EMAIL"), os.getenv("QUOTEX_PASSWORD")
        if not email or not password:
            raise RuntimeError("Credenciais DEMO não configuradas nos secrets do Render.")
        candidate = Quotex(
            email=email, password=password, lang="pt",
            on_otp_callback=_request_otp,
        )
        candidate.set_account_mode("PRACTICE")
        ok, reason = await asyncio.wait_for(candidate.connect(), timeout=max(BROKER_TIMEOUT, 210))
        if not ok:
            raise RuntimeError(f"Falha ao conectar à Quotex: {reason}")
        _client, _connected = candidate, True
        candidate = None
    except Exception as exc:
        log.exception("DEMO connection failed")
        _connected = False
        _client = None
        _connect_error = f"{type(exc).__name__}: {exc}"
    else:
        _connect_error = ""
    finally:
        await _close_client(candidate)
        _connecting = False

@app.get("/api/status")
async def status():
    if _connected:
        message = "Conectado à conta DEMO"
    elif _connecting and _otp_required:
        message = "Aguardando PIN da Quotex"
    elif _connecting:
        message = "Conectando à conta DEMO"
    elif Quotex is None:
        message = "Motor indisponível"
    else:
        message = _connect_error or "Aguardando conexão DEMO"
    return {
        "connected": _connected, "connecting": _connecting,
        "otp_required": _otp_required, "otp_message": _otp_message,
        "package_loaded": Quotex is not None, "account_mode": "PRACTICE",
        "trading_enabled": False, "message": message,
    }

@app.post("/api/connect")
async def connect(payload: ConnectRequest):
    global _connecting, _connect_task, _connect_error
    if not payload.demo:
        raise HTTPException(status_code=403, detail="Somente conexão DEMO/PRACTICE está liberada.")
    if Quotex is None:
        raise HTTPException(status_code=503, detail=f"Biblioteca PyQuotex indisponível: {_IMPORT_ERROR}")
    if _connected:
        return {"connected": True, "account_mode": "PRACTICE"}
    if not _connecting:
        _connect_error = ""
        _connecting = True
        _connect_task = asyncio.create_task(_connect_worker())
    return {"connected": False, "connecting": True, "message": "Processo de conexão iniciado."}

class OTPRequest(BaseModel):
    code: str

@app.post("/api/otp")
async def submit_otp(payload: OTPRequest):
    global _otp_code
    code = payload.code.strip()
    if not code.isdigit() or not 4 <= len(code) <= 8:
        raise HTTPException(status_code=422, detail="Digite um PIN numérico válido (4 a 8 dígitos).")
    if not _otp_required or _otp_event is None:
        raise HTTPException(status_code=409, detail="A Quotex não está aguardando um PIN neste momento.")
    _otp_code = code
    _otp_event.set()
    return {"accepted": True, "message": "PIN recebido. A autenticação continuará."}

@app.post("/api/disconnect")
async def disconnect():
    global _client, _connected
    async with _connect_lock:
        client, _client = _client, None
        _connected = False
        await _close_client(client)
    return {"connected": False}

@app.get("/api/candles")
async def candles(
    asset: str = Query(default="EURUSD", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$"),
    period: int = Query(default=60, ge=1, le=86400),
    limit: int = Query(default=100, ge=1, le=500),
):
    if not _connected or _client is None:
        raise HTTPException(status_code=503, detail="Conecte primeiro a conta DEMO.")
    try:
        data = await asyncio.wait_for(
            _client.get_candles(asset, int(time.time()), limit * period, period), timeout=30)
        candles_data = []
        for item in (data or [])[-limit:]:
            if isinstance(item, dict):
                candles_data.append({
                    "time": item.get("time", item.get("from")),
                    "open": item.get("open"), "high": item.get("high"),
                    "low": item.get("low"), "close": item.get("close"),
                    "volume": item.get("volume", 0),
                })
        return {"asset": asset, "period": period, "candles": candles_data}
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Tempo limite ao buscar candles.") from exc
    except Exception as exc:
        log.exception("Candle retrieval failed for %s", asset)
        raise HTTPException(status_code=502, detail=f"Falha ao obter candles: {type(exc).__name__}: {exc}") from exc

@app.get("/api/assets")
async def assets():
    if not _connected or _client is None:
        return {"assets": [], "connected": False}
    try:
        result = await asyncio.wait_for(_client.get_all_assets(), timeout=30)
        return {"assets": result or [], "connected": True}
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Tempo limite ao listar ativos.") from exc
    except Exception as exc:
        log.exception("Asset listing failed")
        raise HTTPException(status_code=502, detail=f"Falha ao listar ativos: {type(exc).__name__}: {exc}") from exc
