"""PyQuotex-Core API: DEMO-only broker gateway."""
from __future__ import annotations
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Query
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
    return {"name": "PyQuotex-Core API", "status": "ok", "health": "/health", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "ok", "package_loaded": Quotex is not None,
            "connected": _connected, "account_mode": "PRACTICE",
            "trading_enabled": False, "import_error": _IMPORT_ERROR}

@app.get("/api/status")
async def status():
    message = ("Conectado à conta DEMO" if _connected else
               "Motor indisponível" if Quotex is None else "Aguardando conexão DEMO")
    return {"connected": _connected, "package_loaded": Quotex is not None,
            "account_mode": "PRACTICE", "trading_enabled": False, "message": message}

@app.post("/api/connect")
async def connect(payload: ConnectRequest):
    global _client, _connected
    if not payload.demo:
        raise HTTPException(status_code=403, detail="Somente conexão DEMO/PRACTICE está liberada.")
    if Quotex is None:
        raise HTTPException(status_code=503, detail=f"Biblioteca PyQuotex indisponível: {_IMPORT_ERROR}")
    email, password = os.getenv("QUOTEX_EMAIL"), os.getenv("QUOTEX_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="Credenciais DEMO não configuradas nos secrets do Render.")
    async with _connect_lock:
        if _connected and _client is not None:
            return {"connected": True, "account_mode": "PRACTICE"}
        candidate = None
        try:
            candidate = Quotex(email=email, password=password, lang="pt")
            candidate.set_account_mode("PRACTICE")
            ok, reason = await asyncio.wait_for(candidate.connect(), timeout=BROKER_TIMEOUT)
            if not ok:
                await _close_client(candidate)
                raise HTTPException(status_code=502, detail=f"Falha ao conectar à Quotex: {reason}")
            _client, _connected = candidate, True
            return {"connected": True, "account_mode": "PRACTICE"}
        except HTTPException:
            raise
        except asyncio.TimeoutError as exc:
            await _close_client(candidate)
            _client, _connected = None, False
            raise HTTPException(status_code=504, detail="Tempo limite ao conectar. Verifique rede, autenticação e OTP.") from exc
        except Exception as exc:
            await _close_client(candidate)
            _client, _connected = None, False
            log.exception("DEMO connection failed")
            raise HTTPException(status_code=502, detail=f"Erro na conexão DEMO: {type(exc).__name__}: {exc}") from exc

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
