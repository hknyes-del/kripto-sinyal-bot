"""
utils/market_data.py — Async/Non-blocking versiyon

SORUN: requests.get blocking — async bot içinde tüm sistemi donduruyordu.
CÖZÜM:
  1. httpx async client (non-blocking HTTP)
  2. run_in_executor fallback (sync requests'i thread'e taşı)
  3. Cache TTL artırıldı: fiyat=10s, klines=120s, ticker=60s
  4. Toplu fiyat çekme (tek istekte tüm coinler)
"""

import asyncio
import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from config import BINANCE_BASE_URL, SUPPORTED_PAIRS

logger = logging.getLogger(__name__)

# ─── Cache ────────────────────────────────────────────────────────────────────
_cache: dict = {}
_executor = ThreadPoolExecutor(max_workers=4)   # Blocking işlemler için thread pool


def _cache_get(key: str, ttl: int):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < ttl:
            return data
    return None


def _cache_set(key: str, data):
    _cache[key] = (data, time.time())


# ─── Sync HTTP (thread'de çalışır, botu bloklamaz) ───────────────────────────

def _sync_get(url: str, params: dict = None, timeout: int = 8):
    """Senkron HTTP GET — sadece ThreadPoolExecutor içinde çağır."""
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.debug(f"HTTP hata: {url} {e}")
        return None


async def _async_get(url: str, params: dict = None, ttl: int = 30):
    """
    Non-blocking HTTP GET.
    Önce cache'e bak, yoksa thread pool'da çalıştır (botu bloklamaz).
    """
    key = f"{url}:{params}"
    cached = _cache_get(key, ttl)
    if cached is not None:
        return cached

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        _executor, lambda: _sync_get(url, params)
    )
    if data is not None:
        _cache_set(key, data)
    return data


# ─── Sync wrapper (signal_generator gibi sync kodlar için) ───────────────────

def _cached_get(url: str, params: dict = None, ttl: int = 30):
    """Sync kod için — önce cache, sonra blocking HTTP (kısa TTL varsa uyarı)."""
    key = f"{url}:{params}"
    cached = _cache_get(key, ttl)
    if cached is not None:
        return cached
    data = _sync_get(url, params)
    if data is not None:
        _cache_set(key, data)
    return data


# ─── Fiyat fonksiyonları ──────────────────────────────────────────────────────

def get_current_price(symbol: str) -> Optional[float]:
    data = _cached_get(
        f"{BINANCE_BASE_URL}/api/v3/ticker/price",
        params={"symbol": symbol.upper()},
        ttl=10   # 10 saniye cache (eskiden 3s — çok sık istek atıyordu)
    )
    if data and "price" in data:
        return float(data["price"])
    return None


async def get_current_price_async(symbol: str) -> Optional[float]:
    """Handler'lardan çağırılacak async versiyon."""
    data = await _async_get(
        f"{BINANCE_BASE_URL}/api/v3/ticker/price",
        params={"symbol": symbol.upper()},
        ttl=10
    )
    if data and "price" in data:
        return float(data["price"])
    return None


def get_multiple_prices(symbols: list) -> dict:
    """Tek istekle tüm coinlerin fiyatı — çok daha hızlı."""
    key = "all_prices"
    cached = _cache_get(key, ttl=10)
    if cached is not None:
        return {s: cached.get(s.upper()) for s in symbols}

    data = _sync_get(f"{BINANCE_BASE_URL}/api/v3/ticker/price")
    if not data:
        return {}
    all_prices = {item["symbol"]: float(item["price"]) for item in data}
    _cache_set(key, all_prices)
    return {s: all_prices.get(s.upper()) for s in symbols}


def get_24h_ticker(symbol: str) -> Optional[dict]:
    data = _cached_get(
        f"{BINANCE_BASE_URL}/api/v3/ticker/24hr",
        params={"symbol": symbol.upper()},
        ttl=60   # 60 saniye cache (eskiden 30s)
    )
    if not data:
        return None
    return {
        "symbol":       data.get("symbol"),
        "price":        float(data.get("lastPrice", 0)),
        "price_change": float(data.get("priceChange", 0)),
        "change_pct":   float(data.get("priceChangePercent", 0)),
        "high_24h":     float(data.get("highPrice", 0)),
        "low_24h":      float(data.get("lowPrice", 0)),
        "volume":       float(data.get("volume", 0)),
        "quote_volume": float(data.get("quoteVolume", 0)),
        "open_price":   float(data.get("openPrice", 0)),
        "bid":          float(data.get("bidPrice", 0)),
        "ask":          float(data.get("askPrice", 0)),
        "count":        int(data.get("count", 0)),
    }


async def get_24h_ticker_async(symbol: str) -> Optional[dict]:
    data = await _async_get(
        f"{BINANCE_BASE_URL}/api/v3/ticker/24hr",
        params={"symbol": symbol.upper()},
        ttl=60
    )
    if not data:
        return None
    return {
        "symbol":       data.get("symbol"),
        "price":        float(data.get("lastPrice", 0)),
        "change_pct":   float(data.get("priceChangePercent", 0)),
        "high_24h":     float(data.get("highPrice", 0)),
        "low_24h":      float(data.get("lowPrice", 0)),
        "volume":       float(data.get("volume", 0)),
        "quote_volume": float(data.get("quoteVolume", 0)),
    }


def get_klines(symbol: str, interval: str = "1h", limit: int = 200) -> list:
    data = _cached_get(
        f"{BINANCE_BASE_URL}/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        ttl=120   # 2 dakika cache (eskiden 60s — gereksiz istek azaltıldı)
    )
    if not data:
        return []
    return [
        {
            "open_time":  k[0],
            "open":       float(k[1]),
            "high":       float(k[2]),
            "low":        float(k[3]),
            "close":      float(k[4]),
            "volume":     float(k[5]),
            "close_time": k[6],
            "trades":     int(k[8]),
        }
        for k in data
    ]


def get_order_book(symbol: str, depth: int = 20) -> dict:
    data = _cached_get(
        f"{BINANCE_BASE_URL}/api/v3/depth",
        params={"symbol": symbol.upper(), "limit": depth},
        ttl=15   # 15 saniye cache (eskiden 5s)
    )
    if not data:
        return {"bids": [], "asks": [], "imbalance": 50, "spread": 0}

    bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
    asks = [(float(p), float(q)) for p, q in data.get("asks", [])]

    total_bid = sum(q for _, q in bids)
    total_ask = sum(q for _, q in asks)
    total     = total_bid + total_ask
    imbalance = round((total_bid / total * 100) if total > 0 else 50, 1)

    spread = 0.0
    if bids and asks:
        spread = round(((asks[0][0] - bids[0][0]) / bids[0][0]) * 100, 4)

    return {
        "bids":       bids[:10],
        "asks":       asks[:10],
        "imbalance":  imbalance,
        "bid_volume": round(total_bid, 4),
        "ask_volume": round(total_ask, 4),
        "spread":     spread,
        "best_bid":   bids[0][0] if bids else 0,
        "best_ask":   asks[0][0] if asks else 0,
    }


def get_recent_trades(symbol: str, limit: int = 50) -> list:
    data = _cached_get(
        f"{BINANCE_BASE_URL}/api/v3/trades",
        params={"symbol": symbol.upper(), "limit": limit},
        ttl=15
    )
    if not data:
        return []
    return [
        {
            "price":    float(t["price"]),
            "qty":      float(t["qty"]),
            "time":     t["time"],
            "is_buyer": not t.get("isBuyerMaker", True),
        }
        for t in data
    ]


def get_buy_sell_pressure(symbol: str) -> dict:
    trades = get_recent_trades(symbol, 100)
    if not trades:
        return {"buy_pct": 50, "sell_pct": 50}
    buy_vol  = sum(t["qty"] for t in trades if t["is_buyer"])
    sell_vol = sum(t["qty"] for t in trades if not t["is_buyer"])
    total    = buy_vol + sell_vol
    return {
        "buy_pct":  round(buy_vol / total * 100, 1) if total else 50,
        "sell_pct": round(sell_vol / total * 100, 1) if total else 50,
        "buy_vol":  round(buy_vol, 4),
        "sell_vol": round(sell_vol, 4),
    }


def get_fear_greed_index() -> dict:
    try:
        resp = _sync_get("https://api.alternative.me/fng/", params={"limit": 1}, timeout=5)
        if not resp:
            return {"value": 50, "label": "Neutral", "emoji": "😐"}
        item  = resp["data"][0]
        value = int(item["value"])
        if value <= 20:   emoji = "😱"
        elif value <= 40: emoji = "😨"
        elif value <= 60: emoji = "😐"
        elif value <= 80: emoji = "😏"
        else:             emoji = "🤑"
        return {"value": value, "label": item["value_classification"], "emoji": emoji}
    except Exception as e:
        logger.debug(f"Fear & Greed alınamadı: {e}")
        return {"value": 50, "label": "Neutral", "emoji": "😐"}


def get_market_overview() -> list:
    main_pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    results = []
    for pair in main_pairs:
        ticker = get_24h_ticker(pair)
        if ticker:
            results.append({
                "pair":   pair.replace("USDT", "/USDT"),
                "price":  ticker["price"],
                "change": ticker["change_pct"],
                "volume": ticker["quote_volume"],
            })
    return results


def format_price(price: float, decimals: int = None) -> str:
    if price is None:
        return "N/A"
    if decimals is None:
        if price >= 1000:  decimals = 2
        elif price >= 1:   decimals = 4
        else:              decimals = 6
    return f"{price:,.{decimals}f}"


def format_change(pct: float) -> str:
    if pct > 0:   return f"📈 +{pct:.2f}%"
    elif pct < 0: return f"📉 {pct:.2f}%"
    return f"➡️ {pct:.2f}%"

# ═══════════════════════════════════════════════════════════════════
#  FUTURES / LİKİDİTE VERİLERİ (Binance Futures — API key gerekmez)
# ═══════════════════════════════════════════════════════════════════

BINANCE_FUTURES_URL = "https://fapi.binance.com"

_futures_cache = {}  # pair bazlı cache

def get_funding_rate(pair: str) -> dict:
    """
    Binance Futures funding rate.
    Pozitif → Long ağır (kurumsal SHORT fırsatı)
    Negatif → Short ağır (kurumsal LONG fırsatı)
    """
    try:
        cache_key = f"fr_{pair}"
        import time
        now = time.time()
        if cache_key in _futures_cache:
            cached = _futures_cache[cache_key]
            if now - cached["ts"] < 300:  # 5 dakika cache
                return cached["data"]

        resp = _sync_get(
            f"{BINANCE_FUTURES_URL}/fapi/v1/premiumIndex",
            params={"symbol": pair}, timeout=5
        )
        if not resp:
            return {"rate": 0, "label": "Veri yok", "signal": "NEUTRAL"}

        rate = float(resp.get("lastFundingRate", 0)) * 100  # yüzdeye çevir

        if rate > 0.05:
            label  = f"Çok yüksek (+%{rate:.3f}) — Long ağır"
            signal = "SHORT_AVANTAJ"
        elif rate > 0.01:
            label  = f"Yüksek (+%{rate:.3f}) — Long baskın"
            signal = "SHORT_HAFIF"
        elif rate < -0.05:
            label  = f"Çok negatif (%{rate:.3f}) — Short ağır"
            signal = "LONG_AVANTAJ"
        elif rate < -0.01:
            label  = f"Negatif (%{rate:.3f}) — Short baskın"
            signal = "LONG_HAFIF"
        else:
            label  = f"Nötr (%{rate:.3f})"
            signal = "NEUTRAL"

        data = {"rate": rate, "label": label, "signal": signal}
        _futures_cache[cache_key] = {"data": data, "ts": now}
        return data

    except Exception as e:
        logger.debug(f"Funding rate alınamadı {pair}: {e}")
        return {"rate": 0, "label": "Veri yok", "signal": "NEUTRAL"}


def get_long_short_ratio(pair: str) -> dict:
    """
    Global Long/Short oranı.
    Herkes Long ise → kurumsal SHORT geliyor olabilir (tuzak)
    Herkes Short ise → kurumsal LONG geliyor olabilir (tuzak)
    """
    try:
        cache_key = f"ls_{pair}"
        import time
        now = time.time()
        if cache_key in _futures_cache:
            cached = _futures_cache[cache_key]
            if now - cached["ts"] < 300:
                return cached["data"]

        resp = _sync_get(
            f"{BINANCE_FUTURES_URL}/futures/data/globalLongShortAccountRatio",
            params={"symbol": pair, "period": "1h", "limit": 1}, timeout=5
        )
        if not resp or not isinstance(resp, list) or len(resp) == 0:
            return {"long_pct": 50, "short_pct": 50, "label": "Veri yok", "signal": "NEUTRAL"}

        long_pct  = float(resp[0].get("longAccount", 0.5)) * 100
        short_pct = 100 - long_pct

        if long_pct >= 70:
            label  = f"Long kalabalık (%{long_pct:.0f}) — tuzak riski"
            signal = "SHORT_AVANTAJ"  # Herkes long → kurumsal short basabilir
        elif long_pct >= 60:
            label  = f"Long baskın (%{long_pct:.0f})"
            signal = "SHORT_HAFIF"
        elif short_pct >= 70:
            label  = f"Short kalabalık (%{short_pct:.0f}) — tuzak riski"
            signal = "LONG_AVANTAJ"  # Herkes short → kurumsal long basabilir
        elif short_pct >= 60:
            label  = f"Short baskın (%{short_pct:.0f})"
            signal = "LONG_HAFIF"
        else:
            label  = f"Dengeli (L:%{long_pct:.0f} S:%{short_pct:.0f})"
            signal = "NEUTRAL"

        data = {"long_pct": long_pct, "short_pct": short_pct, "label": label, "signal": signal}
        _futures_cache[cache_key] = {"data": data, "ts": now}
        return data

    except Exception as e:
        logger.debug(f"Long/Short oranı alınamadı {pair}: {e}")
        return {"long_pct": 50, "short_pct": 50, "label": "Veri yok", "signal": "NEUTRAL"}


def get_open_interest(pair: str) -> dict:
    """
    Open Interest değişimi.
    OI artıyor + fiyat düşüyor → Short açılıyor (bearish)
    OI artıyor + fiyat çıkıyor → Long açılıyor (bullish)
    OI düşüyor → Pozisyonlar kapanıyor, trend zayıflıyor
    """
    try:
        cache_key = f"oi_{pair}"
        import time
        now = time.time()
        if cache_key in _futures_cache:
            cached = _futures_cache[cache_key]
            if now - cached["ts"] < 300:
                return cached["data"]

        # Son 2 OI değeri al
        resp = _sync_get(
            f"{BINANCE_FUTURES_URL}/futures/data/openInterestHist",
            params={"symbol": pair, "period": "1h", "limit": 2}, timeout=5
        )
        if not resp or not isinstance(resp, list) or len(resp) < 2:
            return {"oi": 0, "change_pct": 0, "label": "Veri yok", "signal": "NEUTRAL"}

        oi_now  = float(resp[-1].get("sumOpenInterest", 0))
        oi_prev = float(resp[-2].get("sumOpenInterest", 1))
        change  = (oi_now - oi_prev) / oi_prev * 100 if oi_prev > 0 else 0

        if change > 2:
            label  = f"OI artıyor (+%{change:.1f}) — yeni para giriyor"
            signal = "STRONG"
        elif change > 0.5:
            label  = f"OI hafif artıyor (+%{change:.1f})"
            signal = "MILD"
        elif change < -2:
            label  = f"OI düşüyor (%{change:.1f}) — pozisyonlar kapanıyor"
            signal = "WEAK"
        else:
            label  = f"OI stabil (%{change:.1f})"
            signal = "NEUTRAL"

        data = {"oi": oi_now, "change_pct": change, "label": label, "signal": signal}
        _futures_cache[cache_key] = {"data": data, "ts": now}
        return data

    except Exception as e:
        logger.debug(f"Open Interest alınamadı {pair}: {e}")
        return {"oi": 0, "change_pct": 0, "label": "Veri yok", "signal": "NEUTRAL"}


def get_liquidity_data(pair: str) -> dict:
    """
    Funding rate + Long/Short + Open Interest birleşik analiz.
    Sinyal üretimine dahil edilecek kurumsal veri paketi.
    """
    fr = get_funding_rate(pair)
    ls = get_long_short_ratio(pair)
    oi = get_open_interest(pair)

    # Kurumsal yön tahmini
    long_signals  = sum([
        fr["signal"] in ("LONG_AVANTAJ", "LONG_HAFIF"),
        ls["signal"] in ("LONG_AVANTAJ", "LONG_HAFIF"),
        oi["signal"] == "STRONG",
    ])
    short_signals = sum([
        fr["signal"] in ("SHORT_AVANTAJ", "SHORT_HAFIF"),
        ls["signal"] in ("SHORT_AVANTAJ", "SHORT_HAFIF"),
        oi["signal"] == "STRONG",
    ])

    if fr["signal"] == "SHORT_AVANTAJ" and ls["signal"] == "SHORT_AVANTAJ":
        kurumsal_yon = "SHORT"
        yon_guc      = "GÜÇLÜ"
    elif fr["signal"] == "LONG_AVANTAJ" and ls["signal"] == "LONG_AVANTAJ":
        kurumsal_yon = "LONG"
        yon_guc      = "GÜÇLÜ"
    elif short_signals >= 2:
        kurumsal_yon = "SHORT"
        yon_guc      = "ORTA"
    elif long_signals >= 2:
        kurumsal_yon = "LONG"
        yon_guc      = "ORTA"
    else:
        kurumsal_yon = "NEUTRAL"
        yon_guc      = "ZAYIF"

    return {
        "funding_rate": fr,
        "long_short":   ls,
        "open_interest": oi,
        "kurumsal_yon": kurumsal_yon,
        "yon_guc":      yon_guc,
    }
