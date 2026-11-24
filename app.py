"""HTTP API for the PyQuotex-Core trading dashboard.

Trading is disabled by default. Configure QUOTEX_EMAIL and QUOTEX_PASSWORD
as Render secret environment variables before enabling a DEMO connection.
"""
from __future__ import annotations

import os
import time
import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from pyquotex.stable_api import Quotex
except Exception as exc:  # keep /health available even if the package fails to load
    Quotex = None  # type: ignore[assignment]
    _IMPORT_ERROR = str(exc)
else:
    _IMPORT_ERROR = None

_client: Any = None
_connected = False
_connect_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _client is not None:
        try:
            await _client.close()
        except Exception:
            pass


app = FastAPI(title="PyQuotex-Core API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ConnectRequest(BaseModel):
    # Credentials should normally be stored in Render env vars, not sent by browser.
    demo: bool = True


class Candle(BaseModel):
    asset: str
    period: int = Field(default=60, ge=1, le=86400)
    limit: int = Field(default=100, ge=1, le=500)


@app.get("/")
async def root():
    return {"name": "PyQuotex-Core API", "status": "ok", "docs": "/docs"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "package_loaded": Quotex is not None,
        "connected": _connected,
        "import_error": _IMPORT_ERROR,
    }


@app.get("/api/status")
async def status():
    return {
        "connected": _connected,
        "account_mode": "PRACTICE",
        "trading_enabled": False,
        "message": "Conexão DEMO ainda não iniciada" if not _connected else "Conectado",
    }


@app.post("/api/connect")
async def connect(payload: ConnectRequest):
    global _client, _connected
    if not payload.demo:
        raise HTTPException(403, "Somente conexão DEMO está liberada nesta versão.")
    if Quotex is None:
        raise HTTPException(503, f"Biblioteca PyQuotex indisponível: {_IMPORT_ERROR}")
    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")
    if not email or not password:
        raise HTTPException(503, "Configure QUOTEX_EMAIL e QUOTEX_PASSWORD nos secrets do Render.")
    async with _connect_lock:
        if _connected:
            return {"connected": True, "account_mode": "PRACTICE"}
        try:
            _client = Quotex(email=email, password=password)
            _client.set_account_mode("PRACTICE")
            ok, reason = await _client.connect()
            if not ok:
                _client = None
                raise HTTPException(502, f"Falha ao conectar à Quotex: {reason}")
            _connected = True
            return {"connected": True, "account_mode": "PRACTICE"}
        except HTTPException:
            raise
        except Exception as exc:
            _client = None
            _connected = False
            raise HTTPException(502, f"Erro na conexão DEMO: {exc}") from exc


@app.post("/api/disconnect")
async def disconnect():
    global _client, _connected
    async with _connect_lock:
        if _client is not None:
            try:
                await _client.close()
            finally:
                _client = None
                _connected = False
    return {"connected": False}


@app.get("/api/candles")
async def candles(
    asset: str = Query(default="EURUSD", min_length=3, max_length=30),
    period: int = Query(default=60, ge=1, le=86400),
    limit: int = Query(default=100, ge=1, le=500),
):
    if not _connected or _client is None:
        raise HTTPException(503, "Conecte primeiro a conta DEMO pela API.")
    end = int(time.time())
    try:
        data = await _client.get_candles(asset, end, limit * period, period)
        if not data:
            return {"asset": asset, "period": period, "candles": []}
        normalized = []
        for item in data[-limit:]:
            if isinstance(item, dict):
                normalized.append({
                    "time": item.get("time", item.get("from")),
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "close": item.get("close"),
                    "volume": item.get("volume", 0),
                })
        return {"asset": asset, "period": period, "candles": normalized}
    except Exception as exc:
        raise HTTPException(502, f"Falha ao obter candles: {exc}") from exc


@app.get("/api/assets")
async def assets():
    if not _connected or _client is None:
        return {"assets": [], "connected": False}
    try:
        return {"assets": await _client.get_all_assets(), "connected": True}
    except Exception as exc:
        raise HTTPException(502, f"Falha ao listar ativos: {exc}") from exc
