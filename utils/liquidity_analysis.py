"""
utils/liquidity_analysis.py — Dinamik Likidite & Manipülasyon Analizi

Kurumsal oyunu okumak için:
1. Tasfiye seviyeleri — hangi kaldıraçta ne kadar para var
2. Likidite yönü — sinyal yönüyle uyumlu mu
3. Manipülasyon tespiti — sahte hareket mi, gerçek mi
4. Kurumsal karar — gir/bekle/atla

Binance Futures public API — API key gerekmez.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

FUTURES_URL = "https://fapi.binance.com"
_liq_cache  = {}  # pair bazlı cache

def _get(url: str, params: dict = None, timeout: int = 5):
    """Basit HTTP GET."""
    try:
        import requests
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.debug(f"HTTP {resp.status_code}: {url}")
        return None
    except Exception as e:
        logger.debug(f"GET hatası {url}: {e}")
        return None


def get_liquidation_levels(pair: str) -> dict:
    """
    Son tasfiye emirlerini analiz eder.
    Hangi yönde daha fazla tasfiye var → kurumsal o yöne gidebilir.
    
    Returns:
        long_liq:  Son 1 saatte tasfiye edilen LONG miktarı (USDT)
        short_liq: Son 1 saatte tasfiye edilen SHORT miktarı (USDT)
        dominant:  Hangi taraf daha fazla tasfiye edildi
        signal:    Kurumsal yön tahmini
    """
    cache_key = f"liq_{pair}"
    now = time.time()
    if cache_key in _liq_cache:
        cached = _liq_cache[cache_key]
        if now - cached["ts"] < 300:  # 5 dk cache
            return cached["data"]

    try:
        # Son tasfiye emirleri
        resp = _get(
            f"{FUTURES_URL}/fapi/v1/allForceOrders",
            params={"symbol": pair, "limit": 200}
        )
        if not resp or not isinstance(resp, list):
            return _empty_liq()

        # Son 1 saatteki tasfiyeleri filtrele
        one_hour_ago = (now - 3600) * 1000  # milisaniye
        recent = [r for r in resp if float(r.get("time", 0)) >= one_hour_ago]

        long_liq  = sum(float(r["origQty"]) * float(r["price"])
                       for r in recent if r.get("side") == "SELL")  # LONG tasfiye → SELL
        short_liq = sum(float(r["origQty"]) * float(r["price"])
                       for r in recent if r.get("side") == "BUY")   # SHORT tasfiye → BUY

        total = long_liq + short_liq
        if total == 0:
            return _empty_liq()

        long_pct  = long_liq  / total * 100
        short_pct = short_liq / total * 100

        # Yorumla
        if long_liq > short_liq * 2:
            dominant = "LONG"
            signal   = "SHORT"  # Long'lar tasfiye ediliyor → kurumsal aşağı itiyor
            label    = f"Long tasfiyesi ağır (${long_liq:,.0f}) — aşağı baskı"
        elif short_liq > long_liq * 2:
            dominant = "SHORT"
            signal   = "LONG"   # Short'lar tasfiye ediliyor → kurumsal yukarı itiyor
            label    = f"Short tasfiyesi ağır (${short_liq:,.0f}) — yukarı baskı"
        else:
            dominant = "NEUTRAL"
            signal   = "NEUTRAL"
            label    = f"Dengeli tasfiye (L:${long_liq:,.0f} S:${short_liq:,.0f})"

        data = {
            "long_liq":  long_liq,
            "short_liq": short_liq,
            "long_pct":  long_pct,
            "short_pct": short_pct,
            "dominant":  dominant,
            "signal":    signal,
            "label":     label,
            "count":     len(recent),
        }
        _liq_cache[cache_key] = {"data": data, "ts": now}
        return data

    except Exception as e:
        logger.debug(f"Tasfiye verisi alınamadı {pair}: {e}")
        return _empty_liq()


def get_manipulation_score(pair: str, direction: str, price: float) -> dict:
    """
    Manipülasyon riski tespiti.
    
    Kontrol edilen şeyler:
    1. Hacim/fiyat uyumsuzluğu — fiyat hareket etmiyor ama hacim yüksek
    2. Funding rate ani değişim — kurumsal pozisyon değiştiriyor
    3. Tasfiye/fiyat ters orantısı — tasfiyeler sinyal yönüne aykırı
    4. Kısa sürede büyük hareket — pump/dump belirtisi
    
    Returns:
        score:   0-100 arası manipülasyon riski (yüksek = riskli)
        signals: Tespit edilen manipülasyon belirtileri
        verdict: TEMIZ / ŞÜPHELI / TEHLİKELİ
    """
    cache_key = f"manip_{pair}_{direction}"
    now = time.time()
    if cache_key in _liq_cache:
        cached = _liq_cache[cache_key]
        if now - cached["ts"] < 120:  # 2 dk cache
            return cached["data"]

    score   = 0
    signals = []

    try:
        from utils.market_data import get_klines

        # 1. Kısa sürede büyük fiyat hareketi — pump/dump
        candles_5m = get_klines(pair, "5m", limit=12)  # Son 1 saat
        if candles_5m and len(candles_5m) >= 6:
            prices   = [c["close"] for c in candles_5m]
            max_p    = max(prices)
            min_p    = min(prices)
            volatil  = (max_p - min_p) / min_p * 100 if min_p > 0 else 0

            if volatil > 5:
                score += 25
                signals.append(f"⚠️ Yüksek volatilite (%{volatil:.1f}) — pump/dump riski")
            elif volatil > 3:
                score += 10
                signals.append(f"⚡ Orta volatilite (%{volatil:.1f})")

        # 2. Hacim/fiyat uyumsuzluğu
        candles_1h = get_klines(pair, "1h", limit=24)
        if candles_1h and len(candles_1h) >= 6:
            vols      = [c.get("volume", 0) for c in candles_1h]
            avg_vol   = sum(vols[:-1]) / len(vols[:-1]) if len(vols) > 1 else 0
            last_vol  = vols[-1]
            prices_1h = [c["close"] for c in candles_1h]
            
            # Son 3 mumda fiyat değişimi
            price_change = abs(prices_1h[-1] - prices_1h[-3]) / prices_1h[-3] * 100 if prices_1h[-3] > 0 else 0

            if avg_vol > 0 and last_vol > avg_vol * 3 and price_change < 0.5:
                # Hacim çok yüksek ama fiyat hareket etmiyor → birikim/dağıtım
                score += 30
                signals.append(f"🔴 Hacim/fiyat uyumsuzluğu — kurumsal birikim veya dağıtım")
            elif avg_vol > 0 and last_vol > avg_vol * 2:
                score += 10
                signals.append(f"⚠️ Hacim normalin 2x üzerinde")

        # 3. Tasfiye yönü sinyal yönüyle uyumlu mu
        liq = get_liquidation_levels(pair)
        if liq["signal"] != "NEUTRAL":
            if liq["signal"] != direction:
                score += 20
                signals.append(f"⚠️ Tasfiye yönü ({liq['signal']}) sinyal yönüyle ({direction}) çelişiyor")
            else:
                score -= 10  # Uyumlu → risk azalır
                signals.append(f"✅ Tasfiye yönü sinyal yönüyle uyumlu")

        # 4. Funding rate aşırı mı
        from utils.market_data import get_funding_rate
        fr = get_funding_rate(pair)
        if abs(fr.get("rate", 0)) > 0.1:
            score += 20
            signals.append(f"🔴 Funding rate aşırı (%{fr['rate']:.3f}) — manipülasyon riski yüksek")
        elif abs(fr.get("rate", 0)) > 0.05:
            score += 10
            signals.append(f"⚠️ Funding rate yüksek (%{fr['rate']:.3f})")

        score = max(0, min(100, score))  # 0-100 arası tut

        if score >= 60:
            verdict = "TEHLİKELİ"
            verdict_em = "🔴"
        elif score >= 30:
            verdict = "ŞÜPHELİ"
            verdict_em = "🟡"
        else:
            verdict = "TEMİZ"
            verdict_em = "🟢"

        data = {
            "score":      score,
            "signals":    signals,
            "verdict":    verdict,
            "verdict_em": verdict_em,
            "liq":        liq,
        }
        _liq_cache[cache_key] = {"data": data, "ts": now}
        return data

    except Exception as e:
        logger.debug(f"Manipülasyon analizi hatası {pair}: {e}")
        return {"score": 0, "signals": [], "verdict": "TEMIZ", "verdict_em": "🟢", "liq": _empty_liq()}


def analyze_liquidity_for_signal(signal: dict) -> dict:
    """
    Sinyal için tam likidite + manipülasyon analizi.
    Sinyal AI'larına veri sağlar.
    
    Returns:
        karar:        GİR / BEKLE / ATLA
        özet:         Kısa açıklama
        detaylar:     Tüm analiz detayları
        manip_score:  Manipülasyon riski
    """
    pair      = signal.get("pair", "")
    direction = signal.get("direction", "")
    price     = float(signal.get("current_price", 0))

    if not pair or not direction:
        return {"karar": "BEKLE", "özet": "Veri eksik", "detaylar": [], "manip_score": 0}

    detaylar  = []
    karar     = "GİR"
    puan      = 0  # Pozitif = GİR, Negatif = ATLA

    # 1. Tasfiye analizi
    liq = get_liquidation_levels(pair)
    if liq["signal"] == direction:
        puan += 20
        detaylar.append(f"✅ Tasfiye {direction} yönünde — kurumsal uyumlu")
    elif liq["signal"] != "NEUTRAL" and liq["signal"] != direction:
        puan -= 20
        detaylar.append(f"⚠️ Tasfiye {liq['signal']} yönünde — sinyal yönüne karşı")
    if liq.get("label") and liq["label"] != "Veri yok":
        detaylar.append(f"💧 {liq['label']}")

    # 2. Manipülasyon analizi
    manip = get_manipulation_score(pair, direction, price)
    detaylar.append(f"{manip['verdict_em']} Manipülasyon: {manip['verdict']} (risk: {manip['score']}/100)")
    for s in manip["signals"][:3]:
        detaylar.append(f"   {s}")

    if manip["score"] >= 60:
        puan -= 30
        karar = "ATLA"
    elif manip["score"] >= 30:
        puan -= 15
        if karar == "GİR":
            karar = "BEKLE"

    # Nihai karar
    if puan >= 15:
        karar = "GİR"
        özet  = f"Likidite uyumlu, manipülasyon riski düşük"
    elif puan >= 0:
        karar = "BEKLE"
        özet  = f"Karışık sinyaller, dikkatli ol"
    else:
        karar = "ATLA"
        özet  = f"Likidite veya manipülasyon riski yüksek"

    return {
        "karar":       karar,
        "özet":        özet,
        "detaylar":    detaylar,
        "manip_score": manip["score"],
        "liq":         liq,
        "puan":        puan,
    }


def _empty_liq() -> dict:
    return {
        "long_liq": 0, "short_liq": 0,
        "long_pct": 50, "short_pct": 50,
        "dominant": "NEUTRAL", "signal": "NEUTRAL",
        "label": "Veri yok", "count": 0,
    }
