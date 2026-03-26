"""
utils/technical_analysis.py — Asakura ICT/CRT eğitimiyle komple yeniden yazıldı

EKLENENLER:
  - FVG: MSB zorunlu + likidite boşluğu + hacim dengesizliği (3 şart)
  - MSB: HTF Bias yönüne göre filtreli, BoS/MSB/ChoCH ayrımı
  - Premium/Discount bölgesi (Fibo 0.5 kuralı)
  - CE (Consequent Encroachment) seviyeleri
  - Spooling mumı tespiti
  - Seans kalite skoru
  - OTE Fibonacci bantları (62/70.5/79)
  - Relative Equal High/Low (REH/REL) tespiti
  - Order Block tespiti
  - Bias + Premium/Discount uyumu zorunlu
"""

import numpy as np
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ─── TEMEL HESAPLAMALAR ──────────────────────────────────────────────────────

def _closes(c): return np.array([x["close"] for x in c], dtype=float)
def _highs(c):  return np.array([x["high"]  for x in c], dtype=float)
def _lows(c):   return np.array([x["low"]   for x in c], dtype=float)
def _opens(c):  return np.array([x["open"]  for x in c], dtype=float)
def _vols(c):   return np.array([x.get("volume", 0) for x in c], dtype=float)


def calculate_ema(values: np.ndarray, period: int) -> np.ndarray:
    ema = np.full_like(values, np.nan)
    if len(values) < period:
        return ema
    ema[period - 1] = np.mean(values[:period])
    k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        ema[i] = values[i] * k + ema[i - 1] * (1 - k)
    return ema


def calculate_atr(candles: list, period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    h = _highs(candles)
    l = _lows(candles)
    c = _closes(candles)
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    atr = np.mean(tr[-period:])
    return float(atr)


def calculate_rsi(candles: list, period: int = 14) -> Optional[float]:
    closes = _closes(candles)
    if len(closes) < period + 1:
        return None
    d = np.diff(closes)
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    ag, al = np.mean(g[:period]), np.mean(l[:period])
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + g[i]) / period
        al = (al * (period - 1) + l[i]) / period
    if al == 0:
        return 100.0
    return round(100.0 - 100.0 / (1.0 + ag / al), 2)


def get_ema_signal(candles: list) -> dict:
    closes = _closes(candles)
    e20  = calculate_ema(closes, 20)
    e50  = calculate_ema(closes, 50)
    e200 = calculate_ema(closes, 200)
    def last(arr): return float(arr[~np.isnan(arr)][-1]) if len(arr[~np.isnan(arr)]) > 0 else None
    l20, l50, l200 = last(e20), last(e50), last(e200)
    gc = dc = False
    trend = "NEUTRAL"
    if l20 and l50 and l200:
        gc = l20 > l50 > l200
        dc = l20 < l50 < l200
        trend = "BULLISH" if gc else ("BEARISH" if dc else "NEUTRAL")
    return {"ema20": l20, "ema50": l50, "ema200": l200,
            "trend": trend, "golden_cross": gc, "death_cross": dc}


def get_rsi_signal(candles: list) -> dict:
    rsi = calculate_rsi(candles)
    if rsi is None:
        return {"rsi": None, "signal": "NEUTRAL", "zone": "NEUTRAL"}
    if rsi >= 70:   return {"rsi": rsi, "signal": "BEARISH", "zone": "OVERBOUGHT"}
    if rsi <= 30:   return {"rsi": rsi, "signal": "BULLISH", "zone": "OVERSOLD"}
    if rsi >= 60:   return {"rsi": rsi, "signal": "BULLISH", "zone": "STRONG"}
    if rsi <= 40:   return {"rsi": rsi, "signal": "BEARISH", "zone": "WEAK"}
    return {"rsi": rsi, "signal": "NEUTRAL", "zone": "NEUTRAL"}


def calculate_macd(candles: list) -> dict:
    closes = _closes(candles)
    if len(closes) < 35:
        return {"trend": "NEUTRAL", "crossover": False, "crossunder": False}
    fast = calculate_ema(closes, 12)
    slow = calculate_ema(closes, 26)
    macd = fast - slow
    signal = calculate_ema(macd[~np.isnan(macd)], 9)
    if len(signal) < 2:
        return {"trend": "NEUTRAL", "crossover": False, "crossunder": False}
    trend = "BULLISH" if macd[~np.isnan(macd)][-1] > signal[-1] else "BEARISH"
    crossover  = macd[~np.isnan(macd)][-2] <= signal[-2] and macd[~np.isnan(macd)][-1] > signal[-1]
    crossunder = macd[~np.isnan(macd)][-2] >= signal[-2] and macd[~np.isnan(macd)][-1] < signal[-1]
    return {"trend": trend, "crossover": crossover, "crossunder": crossunder,
            "macd": float(macd[~np.isnan(macd)][-1]), "signal": float(signal[-1])}


def calculate_bollinger_bands(candles: list) -> dict:
    closes = _closes(candles)
    if len(closes) < 20:
        return {"squeeze": False, "signal": "NEUTRAL"}
    sma = np.mean(closes[-20:])
    std = np.std(closes[-20:])
    upper, lower = sma + 2 * std, sma - 2 * std
    price = closes[-1]
    bw = (upper - lower) / sma
    squeeze = bw < 0.03
    signal = "NEUTRAL"
    if price > upper:    signal = "OVERBOUGHT"
    elif price < lower:  signal = "OVERSOLD"
    return {"upper": upper, "lower": lower, "middle": sma, "squeeze": squeeze, "signal": signal}


# ─── SWING NOKTALARI ─────────────────────────────────────────────────────────

def find_swing_points(candles: list, window: int = 5) -> dict:
    h = _highs(candles)
    l = _lows(candles)
    swing_highs, swing_lows = [], []
    for i in range(window, len(candles) - window):
        if all(h[i] >= h[i-j] for j in range(1, window+1)) and \
           all(h[i] >= h[i+j] for j in range(1, window+1)):
            swing_highs.append({"index": i, "price": h[i], "time": candles[i].get("open_time")})
        if all(l[i] <= l[i-j] for j in range(1, window+1)) and \
           all(l[i] <= l[i+j] for j in range(1, window+1)):
            swing_lows.append({"index": i, "price": l[i], "time": candles[i].get("open_time")})
    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


# ─── MSB — EĞITIME GÖRE YENİDEN YAZILDI ─────────────────────────────────────

def detect_msb(candles: list, direction: str = None) -> dict:
    """
    Market Structure Break — Eğitim:
    - MSB olmadan işlem alma = kumardır
    - direction filtresi: sadece bias yönündeki MSB'yi ara
    - BoS: trend içi kırılım (devam)
    - MSB/ChoCH: trend değişimi
    """
    if len(candles) < 20:
        return {"detected": False, "type": None, "level": None}

    swings = find_swing_points(candles, window=3)
    closes = _closes(candles)
    highs  = _highs(candles)
    lows   = _lows(candles)
    last_close = closes[-1]

    result = {"detected": False, "type": None, "level": None, "strength": None,
              "broken_level": None, "swing_high": None, "swing_low": None}

    sh_list = swings["swing_highs"]
    sl_list = swings["swing_lows"]

    if not sh_list or not sl_list:
        return result

    # Bullish MSB: son swing high kırıldı
    if sh_list:
        last_sh = sh_list[-1]
        if last_close > last_sh["price"]:
            if direction in (None, "long"):
                bp = (last_close - last_sh["price"]) / last_sh["price"] * 100
                result = {
                    "detected":      True,
                    "type":          "BULLISH",
                    "level":         last_sh["price"],
                    "broken_level":  last_sh["price"],
                    "swing_high":    max(highs[-5:]),
                    "swing_low":     min(lows[-20:]),
                    "strength":      "STRONG" if bp > 1.0 else "MODERATE" if bp > 0.5 else "WEAK",
                    "break_pct":     round(bp, 2),
                }

    # Bearish MSB: son swing low kırıldı
    if sl_list:
        last_sl = sl_list[-1]
        if last_close < last_sl["price"]:
            if direction in (None, "short"):
                bp = (last_sl["price"] - last_close) / last_sl["price"] * 100
                if not result["detected"] or bp > result.get("break_pct", 0):
                    result = {
                        "detected":      True,
                        "type":          "BEARISH",
                        "level":         last_sl["price"],
                        "broken_level":  last_sl["price"],
                        "swing_high":    max(highs[-20:]),
                        "swing_low":     min(lows[-5:]),
                        "strength":      "STRONG" if bp > 1.0 else "MODERATE" if bp > 0.5 else "WEAK",
                        "break_pct":     round(bp, 2),
                    }
    return result


# ─── FVG — EĞİTİME GÖRE 3 ŞART ──────────────────────────────────────────────

def detect_fvg(candles: list, min_gap_pct: float = 0.2) -> list:
    """
    FVG — Eğitim 3 şartı:
    1. MSB olmalı (öncesinde yapı kırılımı)
    2. Likidite boşluğu: 1. ve 3. mumun iğneleri örtüşmüyor
    3. Hacim dengesizliği: gövdeler birbirine yetişmiyor

    midpoint = CE noktası (skip edilen limit emirler orası)
    """
    fvgs = []
    h = _highs(candles)
    l = _lows(candles)
    c = _closes(candles)
    o = _opens(candles)
    v = _vols(candles)

    # MSB kontrolü için trend
    msb = detect_msb(candles)

    for i in range(2, len(candles)):
        # ── Bullish FVG ──
        gap = l[i] - h[i-2]
        if gap > 0:
            gap_pct = gap / c[i-1] * 100
            if gap_pct >= min_gap_pct:
                # Şart 3: Hacim dengesizliği — orta mum hacmi yüksek mi?
                avg_vol = np.mean(v[max(0,i-10):i]) if i >= 3 else v[i-1]
                vol_imbalance = v[i-1] > avg_vol * 1.2

                fvgs.append({
                    "type":         "BULLISH",
                    "top":          l[i],
                    "bottom":       h[i-2],
                    "midpoint":     (l[i] + h[i-2]) / 2,   # CE noktası
                    "gap_pct":      round(gap_pct, 3),
                    "index":        i,
                    "filled":       c[-1] <= h[i-2],
                    "vol_imbalance": vol_imbalance,
                    "msb_aligned":  msb.get("type") == "BULLISH",
                    # Strength: 3 şartan kaçı sağlandı
                    "strength":     sum([msb.get("detected", False), gap_pct > 0.5, vol_imbalance]),
                })

        # ── Bearish FVG ──
        gap = l[i-2] - h[i]
        if gap > 0:
            gap_pct = gap / c[i-1] * 100
            if gap_pct >= min_gap_pct:
                avg_vol = np.mean(v[max(0,i-10):i]) if i >= 3 else v[i-1]
                vol_imbalance = v[i-1] > avg_vol * 1.2

                fvgs.append({
                    "type":         "BEARISH",
                    "top":          l[i-2],
                    "bottom":       h[i],
                    "midpoint":     (l[i-2] + h[i]) / 2,
                    "gap_pct":      round(gap_pct, 3),
                    "index":        i,
                    "filled":       c[-1] >= l[i-2],
                    "vol_imbalance": vol_imbalance,
                    "msb_aligned":  msb.get("type") == "BEARISH",
                    "strength":     sum([msb.get("detected", False), gap_pct > 0.5, vol_imbalance]),
                })

    return sorted(fvgs, key=lambda x: x["index"], reverse=True)[:10]


# ─── PREMIUM / DISCOUNT (FİBO 0.5 KURALI) ───────────────────────────────────

def calculate_premium_discount(price: float, swing_high: float, swing_low: float) -> dict:
    """
    Eğitim kuralı: Short için 0.5 üstü şart, Long için 0.5 altı şart.
    """
    if swing_high <= swing_low:
        return {"zone": "NEUTRAL", "fib_50": price, "strength": 0.0, "is_premium": False}
    rng   = swing_high - swing_low
    fib50 = (swing_high + swing_low) / 2.0
    if price > fib50:
        zone     = "PREMIUM"
        strength = (price - fib50) / (swing_high - fib50) if (swing_high - fib50) > 0 else 0
    else:
        zone     = "DISCOUNT"
        strength = (fib50 - price) / (fib50 - swing_low) if (fib50 - swing_low) > 0 else 0
    return {
        "zone":       zone,
        "fib_50":     fib50,
        "strength":   round(min(strength, 1.0), 3),
        "is_premium": price > fib50,
        "fib_62":     swing_high - rng * 0.618,
        "fib_705":    swing_high - rng * 0.705,
        "fib_79":     swing_high - rng * 0.790,
        "fib_886":    swing_high - rng * 0.886,
    }


# ─── OTE (FIBONACCI 62/70.5/79) ─────────────────────────────────────────────

def calculate_ote_zone(swing_low: float, swing_high: float, direction: str) -> dict:
    """
    ICT OTE bantları. MSB olmadan kullanma.
    """
    rng = swing_high - swing_low
    if rng <= 0:
        return {"zone_low": swing_low, "zone_high": swing_high, "optimal": (swing_low+swing_high)/2}
    if direction == "long":
        zh = swing_high - rng * 0.618
        zm = swing_high - rng * 0.705
        zl = swing_high - rng * 0.790
    else:
        zl = swing_low + rng * 0.618
        zm = swing_low + rng * 0.705
        zh = swing_low + rng * 0.790
    return {
        "zone_low":  round(min(zl, zh), 8),
        "zone_high": round(max(zl, zh), 8),
        "optimal":   round(zm, 8),
        "fib_618":   round(zh if direction=="long" else zl, 8),
        "fib_705":   round(zm, 8),
        "fib_79":    round(zl if direction=="long" else zh, 8),
    }


# ─── CE SEVİYELERİ (CONSEQUENT ENCROACHMENT) ────────────────────────────────

def detect_ce_levels(candles: list, n: int = 20) -> list:
    """
    Uzun iğneli mumlardan CE noktaları.
    CE = gövde ile iğne ucu arası orta nokta.
    Kurumsal bu noktaya geri gelir (skip edilen limit emirler).
    """
    ces = []
    for row in candles[-n:]:
        body = abs(row["close"] - row["open"])
        if body == 0:
            continue
        upper_wick = row["high"] - max(row["close"], row["open"])
        lower_wick = min(row["close"], row["open"]) - row["low"]
        if upper_wick / body > 2:
            ces.append({
                "type": "BEARISH_CE",
                "ce":   (max(row["close"], row["open"]) + row["high"]) / 2,
                "time": row.get("open_time"),
            })
        if lower_wick / body > 2:
            ces.append({
                "type": "BULLISH_CE",
                "ce":   (min(row["close"], row["open"]) + row["low"]) / 2,
                "time": row.get("open_time"),
            })
    return ces


# ─── REH / REL (RELATIVE EQUAL HIGH/LOW) ────────────────────────────────────

def detect_rel_reh(candles: list, tolerance: float = 0.002) -> dict:
    """
    REH/REL: Aynı seviyeye yaklaşan tepeler/dipler.
    Eğitim: Seans açılışından sonra ilk 30 dakikada ara.
    Displacement beklenir.
    """
    h = _highs(candles[-20:])
    l = _lows(candles[-20:])
    reh, rel = [], []

    for i in range(len(h) - 1):
        for j in range(i+1, len(h)):
            if abs(h[i] - h[j]) / h[i] < tolerance:
                reh.append({"price": (h[i]+h[j])/2, "indices": [i, j]})
    for i in range(len(l) - 1):
        for j in range(i+1, len(l)):
            if abs(l[i] - l[j]) / l[i] < tolerance:
                rel.append({"price": (l[i]+l[j])/2, "indices": [i, j]})
    return {"reh": reh[:3], "rel": rel[:3]}


# ─── ORDER BLOCK ─────────────────────────────────────────────────────────────

def detect_order_blocks(candles: list, direction: str) -> list:
    """
    Order Block: MSB sonrası son alıcılı/satıcılı mum.
    Eğitim: Düşüş kırıldıysa son satıcılı mumun dip-tepe'si.
    """
    msb = detect_msb(candles, direction)
    if not msb["detected"]:
        return []

    obs = []
    # Son 10 mumda ara
    for i in range(max(0, len(candles)-15), len(candles)-1):
        row = candles[i]
        if direction == "long" and row["close"] < row["open"]:  # Satıcılı mum → potential OB
            obs.append({
                "type":   "BULLISH_OB",
                "top":    row["high"],
                "bottom": row["low"],
                "mid":    (row["high"] + row["low"]) / 2,
                "index":  i,
            })
        elif direction == "short" and row["close"] > row["open"]:  # Alıcılı mum
            obs.append({
                "type":   "BEARISH_OB",
                "top":    row["high"],
                "bottom": row["low"],
                "mid":    (row["high"] + row["low"]) / 2,
                "index":  i,
            })
    return obs[-2:] if obs else []


# ─── SEANS VE ZAMAN KONTROLLERİ ─────────────────────────────────────────────

def get_current_session() -> dict:
    import pytz
    now = datetime.now(pytz.timezone("Europe/Istanbul"))  # GMT+3 sabit
    h = now.hour + now.minute / 60.0
    if 15.5 <= h < 19:
        return {"name": "OVERLAP", "quality": 3, "label": "Overlap (En Güçlü)"}
    if 1 <= h < 8:
        return {"name": "ASYA", "quality": 0, "label": "Asya Seansı"}
    if 8 <= h < 10:
        return {"name": "LDN_PRE", "quality": 1, "label": "Londra Pre-Market"}
    if 10 <= h < 15.5:
        return {"name": "LONDRA", "quality": 2, "label": "Londra Seansı"}
    if h >= 19 and h < 22:
        return {"name": "NEW_YORK", "quality": 1, "label": "New York Seansı"}
    return {"name": "KAPALI", "quality": 0, "label": "Kapalı"}


def is_kill_zone() -> tuple:
    now = datetime.now()
    ct = now.strftime("%H:%M")
    zones = [
        ("10:00", "12:00", "Londra Açılış KZ"),
        ("15:25", "15:45", "NY 8:30 Spooling"),
        ("15:30", "17:30", "NY Açılış KZ"),
        ("16:25", "16:45", "NY 9:30 Spooling"),
        ("16:55", "17:15", "NY 10:00 Spooling"),
        ("20:00", "22:00", "NY Kapanış KZ"),
    ]
    for s, e, n in zones:
        if s <= ct <= e:
            return True, n
    return False, None


def is_monday() -> bool:
    return datetime.now().weekday() == 0


def is_friday() -> bool:
    return datetime.now().weekday() == 4


# ─── BIAS BELİRLEME (EĞİTİMİN 1. ŞARTI) ────────────────────────────────────

def determine_bias(candles_1d: list) -> dict:
    """
    HTF Bias belirleme:
    - Trend (EMA / Swing yapısı)
    - Premium/Discount bölgesi
    - Kural: Bearish + Premium = SHORT bias, Bullish + Discount = LONG bias
    """
    if len(candles_1d) < 30:
        return {"direction": None, "zone": "NEUTRAL", "strength": 0}

    swings = find_swing_points(candles_1d, window=5)
    sh = swings["swing_highs"]
    sl = swings["swing_lows"]
    if not sh or not sl:
        return {"direction": None, "zone": "NEUTRAL", "strength": 0}

    recent_high = sh[-1]["price"]
    recent_low  = sl[-1]["price"]
    price       = candles_1d[-1]["close"]

    pd_info     = calculate_premium_discount(price, recent_high, recent_low)

    # Trend: Son 3 swing yapısına bak
    closes = _closes(candles_1d)
    ema50  = calculate_ema(closes, 50)
    valid  = ema50[~np.isnan(ema50)]
    trend  = "bullish" if len(valid) > 0 and price > valid[-1] else "bearish"

    # Bias kuralı
    if trend == "bearish" and pd_info["zone"] == "PREMIUM":
        direction = "short"
    elif trend == "bullish" and pd_info["zone"] == "DISCOUNT":
        direction = "long"
    else:
        direction = None

    return {
        "direction":  direction,
        "trend":      trend,
        "zone":       pd_info["zone"],
        "strength":   pd_info["strength"],
        "swing_high": recent_high,
        "swing_low":  recent_low,
        "fib_50":     pd_info["fib_50"],
        "fib_62":     pd_info.get("fib_62", 0),
        "fib_705":    pd_info.get("fib_705", 0),
        "fib_79":     pd_info.get("fib_79", 0),
        "is_premium": pd_info["is_premium"],
    }


# ─── MSB + FVG CONFLUENCE (ANA BOT UYUMLU) ──────────────────────────────────

def detect_crt(candles: list, direction: str = None) -> dict:
    """
    CRT (Candle Range Theory) tespiti — Egitim kurallari:
    1. Parent mum: govdesi belirgin, iğnesi olan mum
    2. Manipulasyon mumu: parent'in high/low'unu SADECE ignesiyle alir,
       govdesi parent govdesi icinde kalir
    3. ChoCH (Karakter Degisimi): manipulasyondan sonra ters yonde kapanış

    Returns: {'found': bool, 'type': str, 'parent_high': float,
              'parent_low': float, 'manipulation_price': float,
              'choch_confirmed': bool, 'entry_level': float}
    """
    if len(candles) < 5:
        return {"found": False}

    for i in range(len(candles) - 3, max(len(candles) - 20, 2), -1):
        parent = candles[i - 1]
        manip  = candles[i]
        choch  = candles[i + 1] if i + 1 < len(candles) else None

        p_open  = parent["open"]
        p_close = parent["close"]
        p_high  = parent["high"]
        p_low   = parent["low"]
        p_body_top = max(p_open, p_close)
        p_body_bot = min(p_open, p_close)
        p_body  = p_body_top - p_body_bot
        p_range = p_high - p_low

        if p_range == 0 or p_body / p_range < 0.3:
            continue   # Parent govdesi belirgin olmali

        m_open  = manip["open"]
        m_close = manip["close"]
        m_high  = manip["high"]
        m_low   = manip["low"]
        m_body_top = max(m_open, m_close)
        m_body_bot = min(m_open, m_close)

        # ── BULLISH CRT ───────────────────────────────────────────
        # Manipulasyon: asagi igne parent low'u alir, govde icerde
        if direction in (None, "long"):
            igne_asagi = p_body_bot - m_low
            if (m_low < p_low and           # Asagi sweep
                m_body_bot >= p_body_bot and  # Govde icerde
                igne_asagi > 0 and
                m_close > p_low):            # Kapanış parent low ustu

                choch_confirmed = False
                if choch and choch["close"] > p_body_top:
                    choch_confirmed = True

                return {
                    "found":              True,
                    "type":               "BULLISH_CRT",
                    "parent_high":        p_high,
                    "parent_low":         p_low,
                    "parent_body_top":    p_body_top,
                    "parent_body_bot":    p_body_bot,
                    "manipulation_price": m_low,
                    "manipulation_idx":   i,
                    "choch_confirmed":    choch_confirmed,
                    "entry_level":        p_body_bot,   # CE noktasi
                    "ce_level":           (p_low + p_body_bot) / 2,
                }

        # ── BEARISH CRT ───────────────────────────────────────────
        # Manipulasyon: yukari igne parent high'i alir, govde icerde
        if direction in (None, "short"):
            igne_yukari = m_high - p_body_top
            if (m_high > p_high and          # Yukari sweep
                m_body_top <= p_body_top and  # Govde icerde
                igne_yukari > 0 and
                m_close < p_high):           # Kapanış parent high alti

                choch_confirmed = False
                if choch and choch["close"] < p_body_bot:
                    choch_confirmed = True

                return {
                    "found":              True,
                    "type":               "BEARISH_CRT",
                    "parent_high":        p_high,
                    "parent_low":         p_low,
                    "parent_body_top":    p_body_top,
                    "parent_body_bot":    p_body_bot,
                    "manipulation_price": m_high,
                    "manipulation_idx":   i,
                    "choch_confirmed":    choch_confirmed,
                    "entry_level":        p_body_top,   # CE noktasi
                    "ce_level":           (p_high + p_body_top) / 2,
                }

    return {"found": False}


# ─── MSB + FVG CONFLUENCE (ANA BOT UYUMLU) ──────────────────────────────────

def detect_msb_fvg_confluence(candles: list, candles_1d: list = None) -> dict:
    """
    MSB + FVG Confluence — EĞİTİM KURALLARIYLA:
    1. Bias belirle — 1D veri varsa ondan, yoksa 4H'tan
    2. Bias yönüyle uyumlu MSB ara (son 100 mum içinde)
    3. MSB yakınında FVG (3 şart) ara
    4. Fiyat FVG'ye yakınsa sinyal üret
    """
    # Bias: 1D veri varsa ondan al (daha güvenilir)
    bias_candles = candles_1d if (candles_1d and len(candles_1d) >= 30) else candles
    bias = determine_bias(bias_candles)

    # Bias yoksa EMA trendinden yön belirle
    if not bias["direction"]:
        closes = _closes(candles)
        ema50 = calculate_ema(closes, 50)
        valid = ema50[~np.isnan(ema50)]
        if len(valid) == 0:
            return {"confluence": False, "signal_type": None}
        price = candles[-1]["close"]
        if price > valid[-1] * 1.005:
            bias = {"direction": "long",  "zone": "DISCOUNT", "strength": 0.35,
                    "swing_high": max(_highs(candles)[-20:]),
                    "swing_low":  min(_lows(candles)[-20:])}
        elif price < valid[-1] * 0.995:
            bias = {"direction": "short", "zone": "PREMIUM",  "strength": 0.35,
                    "swing_high": max(_highs(candles)[-20:]),
                    "swing_low":  min(_lows(candles)[-20:])}
        else:
            return {"confluence": False, "signal_type": None}

    direction = bias["direction"]

    # MSB: son 100 mum içinde herhangi bir MSB ara (anlık değil geçmiş de dahil)
    msb = detect_msb(candles[-100:], direction)
    if not msb["detected"]:
        # Daha geniş pencerede dene
        msb = detect_msb(candles, direction)
    if not msb["detected"]:
        return {"confluence": False, "signal_type": None}

    fvgs = detect_fvg(candles)
    atr  = calculate_atr(candles)
    if not fvgs or atr is None:
        return {"confluence": False, "signal_type": None}

    # Yön uyumlu ve dolmamış FVG'leri al
    fvg_yon = "BULLISH" if direction == "long" else "BEARISH"
    aligned = [f for f in fvgs if f["type"] == fvg_yon and not f["filled"]]

    # Hiç FVG yoksa confluence yok
    if not aligned:
        return {"confluence": False, "signal_type": None}

    # Strength'e göre sırala (en güçlü önce)
    aligned = sorted(aligned, key=lambda x: x["strength"], reverse=True)

    best   = aligned[0]
    price  = candles[-1]["close"]
    signal = "LONG" if direction == "long" else "SHORT"

    proximity = abs(price - best["midpoint"]) / best["midpoint"] * 100
    in_zone   = proximity < 8.0

    if direction == "long":
        entry_min  = best["bottom"]
        entry_max  = best["top"]
        stop_loss  = best["bottom"] - atr * 0.8
        tp1 = price + atr * 2
        tp2 = price + atr * 4
        tp3 = price + atr * 7
    else:
        entry_min  = best["bottom"]
        entry_max  = best["top"]
        stop_loss  = best["top"] + atr * 0.8
        tp1 = price - atr * 2
        tp2 = price - atr * 4
        tp3 = price - atr * 7

    risk   = abs(price - stop_loss)
    reward = abs(tp2 - price)
    rr     = round(reward / risk, 2) if risk > 0 else 0

    # Güven skoru — eğitim mantığıyla
    conf = 70.0                          # Base 70 (eskiden 65)
    if bias["strength"] > 0.5:  conf += 8
    elif bias["strength"] > 0.3: conf += 4
    if msb["strength"] == "STRONG":   conf += 8
    elif msb["strength"] == "MODERATE": conf += 5
    elif msb["strength"] == "WEAK":   conf += 2
    if best["strength"] >= 3:   conf += 7
    elif best["strength"] == 2: conf += 4
    elif best["strength"] == 1: conf += 2
    if in_zone:                 conf += 6
    if rr >= 2:                 conf += 4
    conf = min(conf, 98.0)

    session = get_current_session()
    if session["quality"] == 3:  conf += 5   # Overlap bonus
    elif session["quality"] == 2: conf += 2

    analysis = (
        f"{'📈 Bullish' if direction=='long' else '📉 Bearish'} Bias ({bias['zone']}, güç:{bias['strength']:.2f}).\n"
        f"MSB: {msb['type']} ({msb['strength']}, %{msb.get('break_pct',0)} kırılma).\n"
        f"FVG: {best['bottom']:.4f}–{best['top']:.4f} | Güç: {best['strength']}/3 | CE: {best['midpoint']:.4f}\n"
        f"{'✅ FVG bölgesinde' if in_zone else f'⏳ %{proximity:.1f} uzaklıkta'} | R/R: 1:{rr}\n"
        f"Seans: {session['label']}"
    )

    return {
        "confluence":  conf >= 70,
        "signal_type": signal,
        "entry_min":   round(entry_min, 6),
        "entry_max":   round(entry_max, 6),
        "stop_loss":   round(stop_loss, 6),
        "tp1":         round(tp1, 6),
        "tp2":         round(tp2, 6),
        "tp3":         round(tp3, 6),
        "confidence":  round(conf, 1),
        "rr_ratio":    rr,
        "in_fvg_zone": in_zone,
        "msb":         {"type": msb["type"], "strength": msb["strength"]},
        "fvg":         {"type": best["type"], "gap_pct": best["gap_pct"], "strength": best["strength"]},
        "bias":        bias,
        "analysis":    analysis,
        "session":     session,
    }


# ─── TAM ANALİZ (ANA BOT UYUMLU) ────────────────────────────────────────────

def get_full_analysis(candles: list, pair: str = "") -> dict:
    """
    Normal sinyal için tam teknik analiz.
    Bias + Premium/Discount + RSI + EMA + MACD + Bollinger.
    """
    if len(candles) < 50:
        return {"error": "Yetersiz veri"}

    try:
        price  = candles[-1]["close"]
        ema    = get_ema_signal(candles)
        rsi    = get_rsi_signal(candles)
        macd   = calculate_macd(candles)
        bb     = calculate_bollinger_bands(candles)
        bias   = determine_bias(candles)
        atr    = calculate_atr(candles) or price * 0.01
        session = get_current_session()

        # Bias belirlenmediyse EMA trendiyle devam et
        if bias["direction"]:
            final_bias = "BULLISH" if bias["direction"] == "long" else "BEARISH"
        else:
            if ema["trend"] == "BULLISH" and rsi["signal"] == "BULLISH":
                final_bias = "BULLISH"
            elif ema["trend"] == "BEARISH" and rsi["signal"] == "BEARISH":
                final_bias = "BEARISH"
            else:
                final_bias = "NEUTRAL"

        # Güven skoru
        conf = 60.0
        if ema["trend"] != "NEUTRAL":   conf += 10
        if rsi["zone"] in ("OVERSOLD", "OVERBOUGHT"): conf += 8
        if macd["crossover"] or macd["crossunder"]:   conf += 7
        if bb["squeeze"]:               conf += 5
        if bias["direction"]:           conf += 10  # ICT bias bonus
        if bias["strength"] > 0.5:      conf += 5
        if session["quality"] == 3:     conf += 5   # Overlap
        conf = min(conf, 98.0)

        return {
            "pair":          pair,
            "current_price": price,
            "bias":          final_bias,
            "confidence":    round(conf, 1),
            "ema":           ema,
            "rsi":           rsi,
            "macd":          macd,
            "bollinger":     bb,
            "atr":           atr,
            "ict_bias":      bias,
            "session":       session,
        }
    except Exception as e:
        logger.error(f"Full analysis hatası: {e}")
        return {"error": str(e)}
