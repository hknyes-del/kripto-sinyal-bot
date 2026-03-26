"""
utils/signal_generator.py — Asakura ICT/CRT eğitimiyle komple yeniden yazıldı

SINYAL TİPLERİ:
  NORMAL  → EMA/RSI/MACD + Bias + Premium/Discount + Seans filtresi
  MSB_FVG → MSB (yönlü) + FVG (3 şart) + Bias zorunlu
  CRT     → A++ Setup: Bias + Key Level + Premium/Discount + CRT + SMT

YENİ KURALLAR (Eğitimden):
  - Pazartesi işlem yok (Fog of War)
  - SHORT için PREMIUM bölge zorunlu, LONG için DISCOUNT
  - FVG'nin 3 şartı: MSB + likidite boşluğu + hacim dengesizliği
  - Seans filtresi: Overlap en güçlü, Asya en zayıf
  - TGIF (Cuma): ekstra dikkat bayrağı
  - SMT: korele parite uyumsuzluğu (tuz biber)
  - Karakter değişimi doğrulaması
"""

import logging
import random
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from typing import Optional

from config import (
    SUPPORTED_PAIRS, MIN_SIGNAL_CONFIDENCE, TIMEZONE, EMOJI
)
from utils.market_data import get_klines, get_24h_ticker, get_order_book, get_buy_sell_pressure, get_liquidity_data
from utils.liquidity_analysis import analyze_liquidity_for_signal
from utils.technical_analysis import (
    get_full_analysis, detect_msb_fvg_confluence, calculate_atr,
    detect_fvg, detect_msb, determine_bias, calculate_ote_zone,
    detect_ce_levels, detect_order_blocks, detect_rel_reh,
    get_current_session, is_kill_zone, is_monday, is_friday,
    find_swing_points, calculate_premium_discount, detect_crt,
)
from database import save_signal, is_recent_signal_exists

def _fmt(price: float) -> str:
    """Fiyatı dinamik ondalık basamakla formatlar. SHIB gibi küçük coinler için."""
    if price == 0:
        return "0"
    elif price < 0.0001:
        return f"{price:.8f}"
    elif price < 0.01:
        return f"{price:.6f}"
    elif price < 1:
        return f"{price:.4f}"
    elif price < 100:
        return f"{price:.4f}"
    else:
        return f"{price:,.2f}"


# ─── BTC MAKRO BİAS CACHE ────────────────────────────────────────────────────
# BTC haftalık ve günlük trend — her 4 saatte bir güncellenir
_btc_macro_cache = {"bias": None, "updated_at": None}
# ─── NDOG / NWOG CACHE ───────────────────────────────────────────────────────
_gap_cache = {}  # pair bazlı cache: {"BTCUSDT": {"gaps": ..., "updated_at": ...}}

def detect_ndog_nwog(pair: str = "BTCUSDT") -> dict:
    # Slash varsa kaldır: BTC/USDT → BTCUSDT
    pair = pair.replace("/", "")
    """
    NDOG (New Day Opening Gap) ve NWOG (New Week Opening Gap) tespit eder.
    
    NDOG: Her gün 23:45 kapanış → 01:00 açılış arası boşluk
          5 iş günü içinde dolmak ister
    NWOG: Cuma 23:45 → Pazartesi 01:00 arası boşluk  
          5 hafta içinde dolmak ister (daha güçlü mıknatıs)
    
    Returns: {
        "ndog": [{"high": x, "low": y, "ote_0.62": z, "ote_0.705": z, "ote_0.79": z, "date": "..."}],
        "nwog": [{"high": x, "low": y, "ote_0.62": z, ...}],
        "current_price_in_ndog": bool,
        "current_price_in_nwog": bool,
        "nearest_ndog": dict or None,
        "nearest_nwog": dict or None,
        "signal_vs_ndog": "WITH" / "AGAINST" / "NONE",  # sinyalin yönü gap ile uyumlu mu
    }
    """
    from datetime import datetime, timedelta
    import pytz
    
    try:
        now = datetime.utcnow()
        
        # Cache kontrolü — pair bazlı, 1 saatte bir güncelle
        pair_cache = _gap_cache.get(pair, {})
        if (pair_cache.get("gaps") is not None and
            pair_cache.get("updated_at") and
            now - pair_cache["updated_at"] < timedelta(hours=1)):
            return pair_cache["gaps"]
        
        # 15 dakikalık mumlar — Chicago vadeli benzeri yaklaşım için 1h kullanıyoruz
        # 15m mumlar — NDOG 23:45-01:00 arası küçük boşlukları yakalamak için
        candles_15m = get_klines(pair, "15m", limit=500)
        if len(candles_15m) < 50:
            return {"ndog": [], "nwog": [], "current_price_in_ndog": False, 
                    "current_price_in_nwog": False, "nearest_ndog": None, "nearest_nwog": None}
        
        current_price = candles_15m[-1]["close"]
        
        ndog_list = []
        nwog_list = []
        
        # Kripto 7/24 açık — gerçek gap yok
        # NDOG: Her günün 00:00 UTC mumunun high/low'u referans seviye olarak kullanılır
        # NWOG: Her Pazartesi 00:00 UTC mumunun high/low'u
        
        seen_days = set()
        seen_weeks = set()
        
        for i in range(len(candles_15m)-1, 0, -1):
            curr = candles_15m[i]
            curr_time = datetime.utcfromtimestamp(curr["open_time"] / 1000)
            
            day_key  = curr_time.strftime("%Y-%m-%d")
            week_key = curr_time.strftime("%Y-W%W")
            
            # Sadece her günün ilk mumu (00:00 UTC civarı)
            if curr_time.hour != 0 or curr_time.minute >= 15:
                continue
            if day_key in seen_days:
                continue
                
            seen_days.add(day_key)
            
            g_high = curr["high"]
            g_low  = curr["low"]
            g_size = g_high - g_low
            
            if g_size <= 0:
                continue
            
            g_pct = g_size / g_low * 100
            
            gap_info = {
                "high": g_high,
                "low":  g_low,
                "ote_62":  round(g_high - g_size * 0.62, 8),
                "ote_705": round(g_high - g_size * 0.705, 8),
                "ote_79":  round(g_high - g_size * 0.79, 8),
                "direction": "UP" if curr["close"] > curr["open"] else "DOWN",
                "date": curr_time.strftime("%d.%m %H:%M"),
                "gap_pct": round(g_pct, 2),
                "filled": g_low <= current_price <= g_high,
            }
            
            # NWOG: Pazartesi günü
            if curr_time.weekday() == 0 and week_key not in seen_weeks:
                seen_weeks.add(week_key)
                nwog_list.append(gap_info)
            else:
                ndog_list.append(gap_info)
            
            # Yeterli örnek aldıksa dur
            if len(ndog_list) >= 5 and len(nwog_list) >= 2:
                break
        
        # En yakın dolmamış gap'i bul
        def find_nearest(gap_list, price):
            unfilled = [g for g in gap_list if not g["filled"]]
            if not unfilled:
                return None
            # Fiyata en yakın gap
            return min(unfilled, key=lambda g: min(abs(g["high"] - price), abs(g["low"] - price)))
        
        nearest_ndog = find_nearest(ndog_list, current_price)
        nearest_nwog = find_nearest(nwog_list, current_price)
        
        # Fiyat şu an gap içinde mi?
        in_ndog = any(g["low"] <= current_price <= g["high"] for g in ndog_list if not g["filled"])
        in_nwog = any(g["low"] <= current_price <= g["high"] for g in nwog_list if not g["filled"])
        
        result = {
            "ndog": ndog_list[:3],   # Son 3 NDOG
            "nwog": nwog_list[:2],   # Son 2 NWOG
            "current_price_in_ndog": in_ndog,
            "current_price_in_nwog": in_nwog,
            "nearest_ndog": nearest_ndog,
            "nearest_nwog": nearest_nwog,
            "current_price": current_price,
        }
        
        _gap_cache[pair] = {"gaps": result, "updated_at": now}
        
        logger.info(f"📐 NDOG/NWOG: {len(ndog_list)} NDOG, {len(nwog_list)} NWOG tespit edildi")
        return result
        
    except Exception as e:
        logger.warning(f"NDOG/NWOG hesaplanamadı: {e}")
        return {"ndog": [], "nwog": [], "current_price_in_ndog": False,
                "current_price_in_nwog": False, "nearest_ndog": None, "nearest_nwog": None}


def analyze_gap_vs_signal(signal: dict, gap_data: dict) -> dict:
    """
    Sinyalin NDOG/NWOG ile ilişkisini analiz eder.
    
    Returns: {
        "warning": str,       # Uyarı mesajı
        "boost": int,         # Güven artışı/düşüşü (-15 ile +10 arası)
        "ndog_info": str,     # NDOG bilgisi
        "nwog_info": str,     # NWOG bilgisi
    }
    """
    direction = signal.get("direction", "")
    price = signal.get("current_price", 0)
    
    warnings = []
    boost = 0
    ndog_info = ""
    nwog_info = ""
    
    nearest_ndog = gap_data.get("nearest_ndog")
    nearest_nwog = gap_data.get("nearest_nwog")
    
    # NDOG analizi
    if nearest_ndog:
        gap_center = (nearest_ndog["high"] + nearest_ndog["low"]) / 2
        dist_pct = abs(price - gap_center) / price * 100
        
        if not nearest_ndog["filled"]:
            # Gap fiyatın altında → aşağı çeker → SHORT ile uyumlu
            if gap_center < price:
                if direction == "SHORT":
                    boost += 8
                    ndog_info = f"📐 NDOG ({nearest_ndog['date']}) altta — SHORT uyumlu ✅"
                else:  # LONG
                    boost -= 10
                    warnings.append(f"⚠️ NDOG ({nearest_ndog['date']}) altta mıknatıs — LONG riskli")
                    ndog_info = f"📐 NDOG altta mıknatıs ({dist_pct:.1f}% uzakta) ⚠️"
            # Gap fiyatın üstünde → yukarı çeker → LONG ile uyumlu
            else:
                if direction == "LONG":
                    boost += 8
                    ndog_info = f"📐 NDOG ({nearest_ndog['date']}) üstte — LONG uyumlu ✅"
                else:  # SHORT
                    boost -= 10
                    warnings.append(f"⚠️ NDOG ({nearest_ndog['date']}) üstte mıknatıs — SHORT riskli")
                    ndog_info = f"📐 NDOG üstte mıknatıs ({dist_pct:.1f}% uzakta) ⚠️"
    
    # NWOG analizi (daha güçlü — 5 hafta mıknatıs)
    if nearest_nwog:
        gap_center = (nearest_nwog["high"] + nearest_nwog["low"]) / 2
        dist_pct = abs(price - gap_center) / price * 100
        
        if not nearest_nwog["filled"]:
            if gap_center < price:
                if direction == "SHORT":
                    boost += 12
                    nwog_info = f"📅 NWOG ({nearest_nwog['date']}) altta — SHORT güçlü ✅✅"
                else:
                    boost -= 15
                    warnings.append(f"🚨 NWOG ({nearest_nwog['date']}) altta güçlü mıknatıs — LONG çok riskli")
                    nwog_info = f"📅 NWOG altta güçlü mıknatıs ({dist_pct:.1f}% uzakta) 🚨"
            else:
                if direction == "LONG":
                    boost += 12
                    nwog_info = f"📅 NWOG ({nearest_nwog['date']}) üstte — LONG güçlü ✅✅"
                else:
                    boost -= 15
                    warnings.append(f"🚨 NWOG ({nearest_nwog['date']}) üstte güçlü mıknatıs — SHORT çok riskli")
                    nwog_info = f"📅 NWOG üstte güçlü mıknatıs ({dist_pct:.1f}% uzakta) 🚨"
    
    return {
        "warnings": warnings,
        "boost": boost,
        "ndog_info": ndog_info,
        "nwog_info": nwog_info,
    }



def get_btc_macro_bias() -> dict:
    """
    BTC'nin haftalık + günlük bias'ını hesaplar.
    Sonucu 4 saat önbelleğe alır (her sorguda API çağrısı yapmaz).
    Returns: {"trend": "bullish/bearish/neutral", "strength": 0-1, "updated_at": ...}
    """
    from datetime import datetime, timedelta
    now = datetime.utcnow()

    # Önbellekte taze veri varsa döndür
    if (_btc_macro_cache["bias"] is not None and
        _btc_macro_cache["updated_at"] and
        now - _btc_macro_cache["updated_at"] < timedelta(hours=4)):
        return _btc_macro_cache["bias"]

    try:
        # BTC haftalık ve günlük mum verileri
        candles_1w = get_klines("BTCUSDT", "1w", limit=50)
        candles_1d = get_klines("BTCUSDT", "1d", limit=60)

        if len(candles_1w) < 20 or len(candles_1d) < 30:
            return {"trend": "neutral", "strength": 0}

        bias_weekly = determine_bias(candles_1w)
        bias_daily  = determine_bias(candles_1d)

        # İkisi aynı yöndeyse güçlü sinyal
        w_trend = bias_weekly.get("trend", "neutral")
        d_trend = bias_daily.get("trend",  "neutral")

        if w_trend == d_trend == "bearish":
            trend    = "bearish"
            strength = min(bias_weekly.get("strength", 0) + bias_daily.get("strength", 0), 1.0)
        elif w_trend == d_trend == "bullish":
            trend    = "bullish"
            strength = min(bias_weekly.get("strength", 0) + bias_daily.get("strength", 0), 1.0)
        else:
            # Karışık sinyal — haftalık ağırlıklı
            trend    = w_trend if w_trend != "neutral" else d_trend
            strength = max(bias_weekly.get("strength", 0), bias_daily.get("strength", 0)) * 0.5

        result = {
            "trend":          trend,
            "strength":       round(strength, 2),
            "weekly_trend":   w_trend,
            "daily_trend":    d_trend,
            "updated_at":     now.strftime("%H:%M"),
        }

        _btc_macro_cache["bias"]       = result
        _btc_macro_cache["updated_at"] = now

        logger.info(f"📊 BTC Makro Bias: {trend.upper()} (güç:{strength:.2f}) | Haftalık:{w_trend} Günlük:{d_trend}")
        return result

    except Exception as e:
        logger.warning(f"BTC makro bias hesaplanamadı: {e}")
        return {"trend": "neutral", "strength": 0}

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  YARDIMCI: SEVİYE HESAPLAMA
# ═══════════════════════════════════════════════════════════════════

def _calc_levels(direction: str, price: float, atr: float,
                 swing_high: float = None, swing_low: float = None,
                 timeframe: str = "1h") -> tuple:
    """
    Fibonacci Extension bazlı entry/SL/TP seviyeleri.
    Stop Loss: ATR x 0.8
    TP'ler: 15m → ATR bazlı yakın (vur kaç)
            1h/4h → Fibonacci Extension (1.272, 1.618, 2.618)
    """
    sl_mult = 0.8
    entry_w = 0.2

    # CRT — parent candle bazlı TP'ler (ATR x çarpan)
    if timeframe in ("1D + 4H", "1D+4H", "1D+4H (A++)"):
        if direction in ("LONG", "long"):
            stop = round(price - atr * sl_mult, 8)
            risk = price - stop
            return (
                round(price - atr * entry_w, 8),
                round(price + atr * entry_w, 8),
                stop,
                round(price + risk * 2.0, 8),   # TP1 — 2 günde ulaşılabilir
                round(price + risk * 3.5, 8),   # TP2 — orta
                round(price + risk * 5.5, 8),   # TP3 — uzak hedef
            )
        else:
            stop = round(price + atr * sl_mult, 8)
            risk = stop - price
            return (
                round(price - atr * entry_w, 8),
                round(price + atr * entry_w, 8),
                stop,
                round(price - risk * 2.0, 8),
                round(price - risk * 3.5, 8),
                round(price - risk * 5.5, 8),
            )

    # 15m vur kaç — ATR bazlı yakın TP'ler
    if timeframe in ("15m", "15M"):
        if direction == "LONG":
            stop = round(price - atr * sl_mult, 8)
            risk = price - stop
            return (
                round(price - atr * entry_w, 8),
                round(price + atr * entry_w, 8),
                stop,
                round(price + risk * 1.5, 8),  # TP1 — yakın
                round(price + risk * 2.5, 8),  # TP2 — orta
                round(price + risk * 4.0, 8),  # TP3 — uzak
            )
        else:
            stop = round(price + atr * sl_mult, 8)
            risk = stop - price
            return (
                round(price - atr * entry_w, 8),
                round(price + atr * entry_w, 8),
                stop,
                round(price - risk * 1.5, 8),
                round(price - risk * 2.5, 8),
                round(price - risk * 4.0, 8),
            )

    # Fibonacci extension hesapla (swing high/low varsa)
    def fib_tp(swing_h, swing_l, direction, level):
        """Fibonacci extension seviyesi hesaplar."""
        rng = swing_h - swing_l
        decimals = 8 if swing_h < 0.01 else (6 if swing_h < 1 else 4)
        if direction == "LONG":
            return round(swing_l + rng * level, decimals)
        else:
            return round(swing_h - rng * level, decimals)

    if direction == "LONG":
        stop = round(price - atr * sl_mult, 4)
        risk = price - stop

        if swing_high and swing_low and swing_high > swing_low:
            # Fibonacci extension TP'leri
            tp1 = fib_tp(swing_high, swing_low, "LONG", 1.272)
            tp2 = fib_tp(swing_high, swing_low, "LONG", 1.618)
            tp3 = fib_tp(swing_high, swing_low, "LONG", 2.618)
            # OTE giriş zonu (0.62-0.79)
            rng = swing_high - swing_low
            entry_min = round(swing_high - rng * 0.79, 8)
            entry_max = round(swing_high - rng * 0.62, 8)
            # TP mantıklı mı kontrol
            if tp1 > price and tp2 > tp1 and tp3 > tp2:
                return (entry_min, entry_max, stop, tp1, tp2, tp3)

        # Fallback: ATR bazlı
        return (
            round(price - atr * entry_w, 4),
            round(price + atr * entry_w, 4),
            stop,
            round(price + risk * 2.0, 4),
            round(price + risk * 3.0, 4),
            round(price + risk * 5.0, 4),
        )
    else:
        stop = round(price + atr * sl_mult, 4)
        risk = stop - price

        if swing_high and swing_low and swing_high > swing_low:
            tp1 = fib_tp(swing_high, swing_low, "SHORT", 1.272)
            tp2 = fib_tp(swing_high, swing_low, "SHORT", 1.618)
            tp3 = fib_tp(swing_high, swing_low, "SHORT", 2.618)
            rng = swing_high - swing_low
            entry_min = round(swing_low + rng * 0.62, 8)
            entry_max = round(swing_low + rng * 0.79, 8)
            if tp1 < price and tp2 < tp1 and tp3 < tp2:
                return (entry_min, entry_max, stop, tp1, tp2, tp3)

        # Fallback: ATR bazlı
        return (
            round(price - atr * entry_w, 4),
            round(price + atr * entry_w, 4),
            stop,
            round(price - risk * 2.0, 4),
            round(price - risk * 3.0, 4),
            round(price - risk * 5.0, 4),
        )


# ═══════════════════════════════════════════════════════════════════
#  NORMAL SİNYAL
# ═══════════════════════════════════════════════════════════════════

def generate_normal_signal(pair: str = None, timeframe: str = "1h") -> Optional[dict]:
    """
    Normal Sinyal — 3 Timeframe Konfirmasyon (1D + 4H + 1H)
    Tüm timeframe'ler aynı yönü göstermeli.
    Pazartesi işlem yok. SHORT için PREMIUM, LONG için DISCOUNT şart.
    Min 3 gösterge uyumu zorunlu.
    """
    if pair is None:
        pair = random.choice(SUPPORTED_PAIRS[:6])

    if is_monday():
        logger.debug(f"{pair}: Pazartesi Fog of War — sinyal üretilmedi")
        return None

    # ── BTC Makro Filtre ──────────────────────────────────────────────
    btc_macro = get_btc_macro_bias()
    btc_trend = btc_macro.get("trend", "neutral")

    try:
        # ── 3 Timeframe Veri ──────────────────────────────────────────
        candles_1d = get_klines(pair, "1d", limit=60)
        candles_4h = get_klines(pair, "4h", limit=100)
        candles_1h = get_klines(pair, timeframe, limit=200)

        if len(candles_1h) < 100 or len(candles_4h) < 30 or len(candles_1d) < 20:
            return None

        analysis_1d = get_full_analysis(candles_1d, pair)
        analysis_4h = get_full_analysis(candles_4h, pair)
        analysis_1h = get_full_analysis(candles_1h, pair)

        if "error" in analysis_1d or "error" in analysis_4h or "error" in analysis_1h:
            return None

        # ── 3 TF Yön Uyumu — hepsi aynı yönde olmalı ─────────────────
        bias_1d = analysis_1d["bias"]
        bias_4h = analysis_4h["bias"]
        bias_1h = analysis_1h["bias"]

        # En az 2/3 TF uyumu — katı filtre
        bullish_count = sum([bias_1d == "BULLISH", bias_4h == "BULLISH", bias_1h == "BULLISH"])
        bearish_count = sum([bias_1d == "BEARISH", bias_4h == "BEARISH", bias_1h == "BEARISH"])

        if bullish_count >= 2:
            direction = "LONG"
        elif bearish_count >= 2:
            direction = "SHORT"
        else:
            # 2/3 uyum yok — sinyal üretme
            logger.debug(f"{pair}: TF uyumsuzluğu 1D={bias_1d} 4H={bias_4h} 1H={bias_1h} — atlandı")
            return None

        # Ana analiz 1H (göstergeler için)
        analysis = analysis_1h
        price   = analysis["current_price"]
        atr     = analysis.get("atr") or (price * 0.01)
        session = analysis.get("session", {})
        ict     = analysis.get("ict_bias", {})

        # Seans filtresi
        if session.get("quality", 1) == 0:
            return None

        # Bias gücü: 3 TF ortalaması — zorunlu değil, conf etkiler
        str_1d = analysis_1d.get("ict_bias", {}).get("strength", 0)
        str_4h = analysis_4h.get("ict_bias", {}).get("strength", 0)
        str_1h = ict.get("strength", 0)
        avg_bias_strength = (str_1d + str_4h + str_1h) / 3
        # Bias zayıfsa conf düşür ama engelleme
        if avg_bias_strength < 0.25:
            logger.debug(f"{pair}: Bias çok zayıf ({avg_bias_strength:.2f}) — atlandı")
            return None  # Sadece çok zayıfsa engelle

        # Premium/Discount — 1D bias zone esas alınır
        ict_zone_1d = analysis_1d.get("ict_bias", {}).get("zone", "")
        if direction == "SHORT" and ict_zone_1d != "PREMIUM":
            logger.debug(f"{pair}: SHORT ama 1D zone={ict_zone_1d} — atlandı")
            return None
        if direction == "LONG" and ict_zone_1d != "DISCOUNT":
            logger.debug(f"{pair}: LONG ama 1D zone={ict_zone_1d} — atlandı")
            return None

        # ── Gösterge Uyumu — minimum 3 gösterge aynı yönde ───────────
        indicators_aligned = 0
        ema_1h = analysis_1h["ema"]
        rsi_1h = analysis_1h["rsi"]
        macd_1h = analysis_1h["macd"]
        bb_1h = analysis_1h["bollinger"]

        if direction == "LONG":
            if ema_1h["trend"] == "BULLISH":       indicators_aligned += 1
            if rsi_1h["rsi"] > 45:                 indicators_aligned += 1
            if macd_1h.get("trend") == "BULLISH":  indicators_aligned += 1
            if analysis_4h["ema"]["trend"] == "BULLISH": indicators_aligned += 1
            if analysis_1d["ema"]["trend"] == "BULLISH": indicators_aligned += 1
        else:
            if ema_1h["trend"] == "BEARISH":       indicators_aligned += 1
            if rsi_1h["rsi"] < 55:                 indicators_aligned += 1
            if macd_1h.get("trend") == "BEARISH":  indicators_aligned += 1
            if analysis_4h["ema"]["trend"] == "BEARISH": indicators_aligned += 1
            if analysis_1d["ema"]["trend"] == "BEARISH": indicators_aligned += 1

        if indicators_aligned < 2:
            logger.debug(f"{pair}: Gösterge uyumu yetersiz ({indicators_aligned}/5) — atlandı")
            return None

        # Cooldown: aynı coinde 6 saat sinyal yok
        if is_recent_signal_exists(pair, direction, hours=6):
            return None

        # Order flow
        order_book = get_order_book(pair, depth=20)
        pressure   = get_buy_sell_pressure(pair)
        ticker     = get_24h_ticker(pair)

        conf = analysis["confidence"]

        # RSI filtresi
        rsi_zone = analysis["rsi"]["zone"]
        rsi_val  = float(analysis["rsi"]["rsi"] or 50)

        # RSI aşırı bölge — return None yerine conf cezası
        if rsi_val < 25 and direction == "SHORT":
            logger.debug(f"{pair}: RSI çok aşırı satılmış ({rsi_val:.1f}) + SHORT — atlandı")
            return None  # Sadece çok aşırıda engelle
        elif rsi_val < 35 and direction == "SHORT":
            conf = max(conf - 10, 0)  # Conf cezası

        if rsi_val > 75 and direction == "LONG":
            logger.debug(f"{pair}: RSI çok aşırı alınmış ({rsi_val:.1f}) + LONG — atlandı")
            return None  # Sadece çok aşırıda engelle
        elif rsi_val > 65 and direction == "LONG":
            conf = max(conf - 10, 0)  # Conf cezası

        if rsi_zone in ("STRONG", "OVERSOLD")  and direction == "LONG":  conf += 5
        if rsi_zone in ("WEAK",   "OVERBOUGHT") and direction == "SHORT": conf += 5

        if analysis["bollinger"]["squeeze"]: conf += 5

        if direction == "LONG"  and pressure["buy_pct"]  > 55: conf += 5
        if direction == "SHORT" and pressure["sell_pct"] > 55: conf += 5
        if order_book["imbalance"] > 65 and direction == "LONG":  conf += 3
        if order_book["imbalance"] < 35 and direction == "SHORT": conf += 3

        # Seans bonus
        sq = session.get("quality", 1)
        if sq == 3:   conf += 5    # Overlap
        elif sq == 2: conf += 2

        # TGIF bayrağı
        tgif_flag = is_friday()
        if tgif_flag: conf += 3    # Cuma kapanış likiditesi

        if ticker:
            avg_vol  = ticker["volume"] / 24
            last_vol = candles_1h[-1]["volume"]
            if last_vol > avg_vol * 1.5: conf += 4

        conf = min(conf, 98.0)
        if conf < MIN_SIGNAL_CONFIDENCE:
            return None

        # ── BTC Makro Filtre ──────────────────────────────────────────
        # BTC trend ile çelişen sinyallerde güven düşürülür, engellenmez
        btc_str = btc_macro.get("strength", 0)
        if btc_trend == "bearish" and direction == "LONG":
            penalty = 25 if btc_str >= 0.8 else 15
            conf = max(conf - penalty, 0)
            logger.debug(f"{pair}: BTC makro BEARISH, LONG güven -{penalty}: {conf:.0f}")
        elif btc_trend == "bullish" and direction == "SHORT":
            penalty = 25 if btc_str >= 0.8 else 15
            conf = max(conf - penalty, 0)
            logger.debug(f"{pair}: BTC makro BULLISH, SHORT güven -{penalty}: {conf:.0f}")

        if conf < MIN_SIGNAL_CONFIDENCE:
            return None

        # Swing high/low — fibonacci için
        swings    = find_swing_points(candles_4h, window=5)
        s_high    = swings["swing_highs"][-1]["price"] if swings["swing_highs"] else None
        s_low     = swings["swing_lows"][-1]["price"]  if swings["swing_lows"]  else None

        entry_min, entry_max, stop_loss, tp1, tp2, tp3 = _calc_levels(direction, price, atr, s_high, s_low, timeframe=timeframe)

        rr_ratio = round(abs(tp2 - price) / abs(price - stop_loss), 2) if abs(price - stop_loss) > 0 else 2.0

        # Minimum R/R filtresi — 1:1.5 altı sinyal gönderme
        if rr_ratio < 1.3:
            logger.debug(f"{pair}: R/R çok düşük ({rr_ratio}) — atlandı")
            return None

        indicators = {
            "ema_trend":  analysis["ema"]["trend"],
            "rsi":        analysis["rsi"]["rsi"],
            "rsi_zone":   rsi_zone,
            "macd_trend": analysis["macd"]["trend"],
            "bb_signal":  analysis["bollinger"]["signal"],
            "buy_pressure": pressure["buy_pct"],
            "session":    session.get("label", ""),
            "ict_zone":   ict.get("zone", ""),
            "tgif":       tgif_flag,
        }

        active = []
        if analysis["ema"]["golden_cross"]: active.append("EMA Golden Cross ✨")
        if analysis["ema"]["death_cross"]:  active.append("EMA Death Cross 💀")
        if analysis["macd"]["crossover"]:   active.append("MACD Bullish Cross 📈")
        if analysis["macd"]["crossunder"]:  active.append("MACD Bearish Cross 📉")
        if rsi_zone == "OVERSOLD":          active.append("RSI Oversold 🔥")
        if rsi_zone == "OVERBOUGHT":        active.append("RSI Overbought ⚠️")
        if analysis["bollinger"]["squeeze"]: active.append("BB Squeeze 💥")
        if tgif_flag:                        active.append("📅 TGIF — Cuma likiditesi")
        if ict.get("zone"):                  active.append(f"ICT Bias: {ict_zone_1d} ({direction})")

        analysis_text = (
            f"{'🟢 LONG' if direction=='LONG' else '🔴 SHORT'} — {session.get('label', '')}\n\n"
            f"📊 Aktif Göstergeler:\n"
            + "\n".join([f"  • {s}" for s in active[:6]]) + "\n\n"
            f"📈 EMA Trendi: {analysis['ema']['trend']}\n"
            f"💹 RSI: {analysis['rsi']['rsi']} ({rsi_zone})\n"
            f"📊 ICT Bias: {ict_zone_1d} / Güç: {str_1d:.2f}\n"
        )

        # ── Kurumsal Likidite Verisi (Funding Rate + L/S + OI) ────────
        try:
            liq_data = get_liquidity_data(pair)
        except Exception:
            liq_data = {"kurumsal_yon": "NEUTRAL", "yon_guc": "ZAYIF",
                        "funding_rate": {}, "long_short": {}, "open_interest": {}}

        # Kurumsal yön sinyal yönüyle çelişiyorsa güven düşür
        kurumsal_yon = liq_data.get("kurumsal_yon", "NEUTRAL")
        yon_guc      = liq_data.get("yon_guc", "ZAYIF")
        if kurumsal_yon != "NEUTRAL" and kurumsal_yon != direction and yon_guc == "GÜÇLÜ":
            penalty = 15
            conf = max(conf - penalty, 0)
            logger.debug(f"{pair}: Kurumsal yön {kurumsal_yon} ≠ {direction} — güven -{penalty}")
        elif kurumsal_yon == direction and yon_guc == "GÜÇLÜ":
            conf = min(conf + 5, 100)  # Uyumlu ise küçük boost

        # ── NDOG/NWOG Analizi (sadece bilgi, filtreleme yok) ──────────
        gap_data = detect_ndog_nwog(pair)
        if indicators is None:
            indicators = {}
        indicators["ndog_count"] = len(gap_data.get("ndog", []))
        indicators["nwog_count"] = len(gap_data.get("nwog", []))
        indicators["nearest_ndog"] = gap_data.get("nearest_ndog")
        indicators["nearest_nwog"] = gap_data.get("nearest_nwog")
        indicators["price_in_ndog"] = gap_data.get("current_price_in_ndog", False)
        indicators["price_in_nwog"] = gap_data.get("current_price_in_nwog", False)

        # Geçerlilik süresi — 15m: 2 saat, 1h: 8 saat, 4h: 24 saat
        expires_h = 2 if timeframe in ("15m", "15M") else (8 if timeframe in ("1h", "1H") else 24)

        # Fiyat bazlı iptal seviyesi
        if direction == "LONG":
            invalidation_price = round(entry_min * 0.98, 8)  # zona %2 altı kırılırsa iptal
        else:
            invalidation_price = round(entry_max * 1.02, 8)  # zona %2 üstü kırılırsa iptal

        signal_id = save_signal(
            signal_type="NORMAL", pair=pair, direction=direction,
            entry_min=entry_min, entry_max=entry_max, stop_loss=stop_loss,
            tp1=tp1, tp2=tp2, tp3=tp3, confidence=conf,
            timeframe=timeframe, indicators=indicators,
            analysis_text=analysis_text, rr_ratio=rr_ratio,
            expires_in_hours=expires_h,
        )
        gap_analysis = analyze_gap_vs_signal(
            {"direction": direction, "current_price": price}, gap_data
        )

        result = {
            "id": signal_id, "type": "NORMAL", "pair": pair,
            "direction": direction, "timeframe": timeframe,
            "entry_min": entry_min, "entry_max": entry_max,
            "stop_loss": stop_loss, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "rr_ratio": rr_ratio, "confidence": conf,
            "indicators": indicators, "analysis": analysis_text,
            "current_price": price,
            "created_at": datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
            "tgif": tgif_flag,
            "session": session.get("label", ""),
            "bias": {
                "zone":     ict_zone_1d,
                "strength": analysis_1d.get("ict_bias", {}).get("strength", 0),
                "direction": direction,
            },
            "ndog_info": gap_analysis.get("ndog_info", ""),
            "nwog_info": gap_analysis.get("nwog_info", ""),
            "gap_warnings": gap_analysis.get("warnings", []),
            "gap_boost": gap_analysis.get("boost", 0),
            "liquidity": liq_data,
            "expires_in_hours": expires_h,
            "invalidation_price": invalidation_price,
        }

        # Likidite + manipülasyon analizi — sinyal dict'e ekle
        try:
            liq_analiz = analyze_liquidity_for_signal(result)
            result["liq_analiz"] = liq_analiz
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"Normal sinyal hatası ({pair}): {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
#  MSB + FVG SİNYALİ
# ═══════════════════════════════════════════════════════════════════

def generate_msb_fvg_signal(pair: str = None, timeframe: str = "4h") -> Optional[dict]:
    """
    MSB + FVG — Eğitim kurallarıyla:
    - Bias zorunlu (gücü min 0.30)
    - FVG 3 şartı kontrol
    - Premium/Discount filtresi
    """
    if pair is None:
        pair = random.choice(SUPPORTED_PAIRS[:6])

    # Stablecoin filtresi
    STABLECOIN_BLACKLIST = {
        "USDCUSDT","FDUSDUSDT","PAXGUSDT","USD1USDT","BUSDUSDT",
        "TUSDUSDT","USDPUSDT","DAIUSDT","USDEUSDT","RLUSDUSDT",
        "EULUSDT","XUSDUSDT","BFUSDUSDT","EURUSDT",
    }
    if pair in STABLECOIN_BLACKLIST:
        return None

    if is_monday():
        return None

    # ── BTC Makro Filtre ──────────────────────────────────────────────
    btc_macro = get_btc_macro_bias()
    btc_trend = btc_macro.get("trend", "neutral")

    try:
        candles    = get_klines(pair, timeframe, limit=200)
        candles_1d = get_klines(pair, "1d", limit=60)
        if len(candles) < 50:
            return None

        session = get_current_session()
        if session["quality"] == 0:
            return None  # Asya seansı

        # 1D bias ile confluence (daha güvenilir yön tespiti)
        confluence = detect_msb_fvg_confluence(candles, candles_1d)
        if not confluence["confluence"]:
            return None

        # MSB_FVG için eşik 75 (NORMAL'den düşük — yapısal sinyal olduğu için)
        if confluence["confidence"] < 75:
            return None

        # Minimum R/R filtresi
        if confluence.get("rr_ratio", 0) < 1.3:
            logger.debug(f"{pair}: MSB_FVG R/R düşük ({confluence.get('rr_ratio',0)}) — atlandı")
            return None

        # Bias gücü minimum 0.35 (SHORT için 0.40)
        bias_str = confluence.get("bias", {}).get("strength", 0)
        msb_dir  = confluence.get("signal_type", "")
        min_bias_msb = 0.40 if msb_dir == "SHORT" else 0.35
        if bias_str < min_bias_msb:
            logger.debug(f"{pair}: MSB_FVG bias gücü düşük ({bias_str:.2f} < {min_bias_msb}) — atlandı")
            return None

        # BTC makro trend filtresi — engelleme yok, güven düşürülür
        signal_dir = confluence.get("signal_type", "").lower()
        btc_str = btc_macro.get("strength", 0)
        if btc_trend == "bearish" and "long" in signal_dir:
            penalty = 25 if btc_str >= 0.8 else 15
            logger.debug(f"{pair}: MSB_FVG — BTC makro BEARISH, LONG güven -{penalty}")
        elif btc_trend == "bullish" and "short" in signal_dir:
            penalty = 25 if btc_str >= 0.8 else 15
            logger.debug(f"{pair}: MSB_FVG — BTC makro BULLISH, SHORT güven -{penalty}")

        # MSB gücü WEAK ise geçme
        if confluence.get("msb", {}).get("strength") == "WEAK":
            logger.debug(f"{pair}: MSB_FVG MSB çok zayıf — atlandı")
            return None

        if is_recent_signal_exists(pair, confluence["signal_type"], hours=4):
            return None

        # 1H çapraz onay
        candles_1h   = get_klines(pair, "1h", limit=100)
        analysis_1h  = get_full_analysis(candles_1h, pair) if len(candles_1h) >= 50 else None
        extra = 0
        if analysis_1h and "error" not in analysis_1h:
            if confluence["signal_type"] == "LONG"  and analysis_1h["bias"] == "BULLISH": extra = 5
            elif confluence["signal_type"] == "SHORT" and analysis_1h["bias"] == "BEARISH": extra = 5

        final_conf = min(confluence["confidence"] + extra, 98.0)

        # Kill Zone bonus
        kz, kz_name = is_kill_zone()
        if kz: final_conf = min(final_conf + 3, 98.0)

        # ── NDOG/NWOG Analizi (sadece bilgi, filtreleme yok) ──────────
        _price_msb = candles[-1]["close"]
        gap_data_msb = detect_ndog_nwog(pair)

        # MSB_FVG geçerlilik: 4h = 24 saat, 1h = 12 saat
        msb_expires = 12 if timeframe == "1h" else 24

        # Fiyat bazlı iptal
        msb_dir = confluence["signal_type"]
        if msb_dir == "LONG":
            invalidation_price = round(confluence["entry_min"] * 0.98, 8)
        else:
            invalidation_price = round(confluence["entry_max"] * 1.02, 8)

        signal_id = save_signal(
            signal_type="MSB_FVG", pair=pair,
            direction=confluence["signal_type"],
            entry_min=confluence["entry_min"],
            entry_max=confluence["entry_max"],
            stop_loss=confluence["stop_loss"],
            tp1=confluence["tp1"], tp2=confluence["tp2"], tp3=confluence["tp3"],
            confidence=final_conf, timeframe=f"{timeframe}→1H",
            indicators={
                "msb_type":       confluence["msb"]["type"],
                "msb_strength":   confluence["msb"]["strength"],
                "fvg_type":       confluence["fvg"]["type"],
                "fvg_gap_pct":    confluence["fvg"]["gap_pct"],
                "fvg_strength":   confluence["fvg"]["strength"],
                "in_fvg_zone":    confluence["in_fvg_zone"],
                "bias_zone":      confluence.get("bias", {}).get("zone", ""),
                "tf_confirmation": extra > 0,
                "kill_zone":      kz,
                "session":        session["label"],
                "ndog_count":     len(gap_data_msb.get("ndog", [])),
                "nwog_count":     len(gap_data_msb.get("nwog", [])),
                "nearest_ndog":   gap_data_msb.get("nearest_ndog"),
                "nearest_nwog":   gap_data_msb.get("nearest_nwog"),
                "price_in_ndog":  gap_data_msb.get("current_price_in_ndog", False),
                "price_in_nwog":  gap_data_msb.get("current_price_in_nwog", False),
            },
            analysis_text=confluence["analysis"],
            rr_ratio=confluence["rr_ratio"],
        )
        gap_analysis_msb = analyze_gap_vs_signal(
            {"direction": confluence["signal_type"], "current_price": _price_msb}, gap_data_msb
        )
        _adj_conf = final_conf  # boost uygulanmıyor

        msb_result = {
            "id": signal_id, "type": "MSB_FVG", "pair": pair,
            "direction": confluence["signal_type"],
            "timeframe": f"{timeframe.upper()} → 1H Onayı",
            "entry_min": confluence["entry_min"],
            "entry_max": confluence["entry_max"],
            "stop_loss": confluence["stop_loss"],
            "tp1": confluence["tp1"], "tp2": confluence["tp2"], "tp3": confluence["tp3"],
            "rr_ratio": confluence["rr_ratio"],
            "confidence": _adj_conf,
            "msb": confluence["msb"],
            "fvg": confluence["fvg"],
            "bias": confluence.get("bias", {}),
            "analysis": confluence["analysis"],
            "current_price": _price_msb,
            "created_at": datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
            "session": session["label"],
            "kill_zone": kz_name if kz else None,
            "ndog_info": gap_analysis_msb.get("ndog_info", ""),
            "nwog_info": gap_analysis_msb.get("nwog_info", ""),
            "gap_warnings": gap_analysis_msb.get("warnings", []),
            "gap_boost": gap_analysis_msb.get("boost", 0),
            "expires_in_hours": msb_expires,
            "invalidation_price": invalidation_price,
        }

        # Likidite + manipülasyon analizi
        try:
            msb_result["liq_analiz"] = analyze_liquidity_for_signal(msb_result)
        except Exception:
            pass

        return msb_result

    except Exception as e:
        logger.error(f"MSB+FVG sinyal hatası ({pair}): {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
#  CRT A++ SİNYALİ
# ═══════════════════════════════════════════════════════════════════

def generate_crt_signal(pair: str = None) -> Optional[dict]:
    """
    A++ CRT Sinyali — Asakura eğitiminin tüm 5 şartı:
    1. Bias (yüksek TF)
    2. Key Level teması (FVG/OB)
    3. Premium/Discount bölgesi
    4. CRT yapısı + karakter değişimi
    5. SMT uyumsuzluğu (opsiyonel — tuz biber)
    """
    if pair is None:
        pair = random.choice(SUPPORTED_PAIRS[:10])

    # Stablecoin filtresi
    STABLECOIN_BLACKLIST = {
        "USDCUSDT","FDUSDUSDT","PAXGUSDT","USD1USDT","BUSDUSDT",
        "TUSDUSDT","USDPUSDT","DAIUSDT","USDEUSDT","RLUSDUSDT",
        "EULUSDT","XUSDUSDT","BFUSDUSDT","EURUSDT",
    }
    if pair in STABLECOIN_BLACKLIST:
        return None

    # Pazartesi CRT sinyalleri aktif — 1D+4H timeframe Fog of War'dan etkilenmez
    # NORMAL ve MSB_FVG Pazartesi kapalı

    # ── BTC Makro Filtre ──────────────────────────────────────────────
    btc_macro = get_btc_macro_bias()
    btc_trend = btc_macro.get("trend", "neutral")

    try:
        # Veri çek
        candles_1d = get_klines(pair, "1d", limit=100)
        candles_4h = get_klines(pair, "4h", limit=200)
        if len(candles_1d) < 30 or len(candles_4h) < 100:
            return None

        session = get_current_session()
        if session["quality"] == 0:
            return None  # Asya seansı

        # ── Adım 1: Bias ─────────────────────────────
        bias = determine_bias(candles_1d)
        if not bias["direction"]:
            return None

        direction = bias["direction"]
        direction_str = "LONG" if direction == "long" else "SHORT"

        # ── Adım 2: Premium/Discount kontrolü ────────
        if direction == "short" and bias["zone"] != "PREMIUM":
            return None
        if direction == "long" and bias["zone"] != "DISCOUNT":
            return None

        # ── Adım 3: CRT Yapısı (4H) ──────────────────
        # Önce bias yönünde CRT ara, yoksa her iki yönde ara
        crt_result = detect_crt(candles_4h, direction=direction)
        if not crt_result.get("found"):
            # Bias yönünde CRT yoksa, tüm CRT'leri ara
            crt_result = detect_crt(candles_4h, direction=None)
        if not crt_result.get("found"):
            return None

        # CRT kendi yönünü belirler — bias değil
        crt_type = crt_result.get("type", "")
        if crt_type == "BULLISH_CRT":
            direction = "long"
            direction_str = "LONG"
        elif crt_type == "BEARISH_CRT":
            direction = "short"
            direction_str = "SHORT"

        # ── Adım 4: Key Level (FVG/OB) ───────────────
        fvgs = detect_fvg(candles_4h)
        obs  = detect_order_blocks(candles_4h, direction)
        has_key_level = bool(fvgs) or bool(obs)
        if not has_key_level:
            return None   # Key Level olmadan A++ olmaz

        # ── Adım 5: SMT (opsiyonel — tuz biber) ──────
        smt = None
        corr_map = {
            "BTCUSDT": "ETHUSDT", "ETHUSDT": "BTCUSDT",
            "SOLUSDT": "AVAXUSDT",
        }
        corr_pair = corr_map.get(pair)
        if corr_pair:
            try:
                c_corr = get_klines(corr_pair, "4h", limit=50)
                if len(c_corr) >= 20:
                    # Basit SMT: son 10 mumda biri yeni high/low yaparken diğeri yapmıyor
                    main_highs = [c["high"] for c in candles_4h[-10:]]
                    corr_highs = [c["high"] for c in c_corr[-10:]]
                    main_lows  = [c["low"]  for c in candles_4h[-10:]]
                    corr_lows  = [c["low"]  for c in c_corr[-10:]]
                    if direction == "long":
                        # Ana parite yeni low, korele parite yapmıyor = bullish SMT
                        if min(main_lows) < min(main_lows[:-1]) and min(corr_lows) >= min(corr_lows[:-1]):
                            smt = {"type": "BULLISH_SMT", "direction": "long"}
                    else:
                        # Ana parite yeni high, korele parite yapmıyor = bearish SMT
                        if max(main_highs) > max(main_highs[:-1]) and max(corr_highs) <= max(corr_highs[:-1]):
                            smt = {"type": "BEARISH_SMT", "direction": "short"}
            except:
                pass

        # ── Güven skoru ──────────────────────────────
        analysis_1d = get_full_analysis(candles_1d, pair)
        analysis_4h = get_full_analysis(candles_4h, pair)
        conf = (analysis_1d.get("confidence", 70) + analysis_4h.get("confidence", 70)) / 2

        if crt_result.get("choch_confirmed"):   conf += 10
        if smt:                                  conf += 10   # Tuz-biber
        if session["quality"] == 3:              conf += 5    # Overlap
        elif session["quality"] == 2:            conf += 2
        if bias["strength"] > 0.6:               conf += 5
        conf = min(conf + 5, 98.0)

        if conf < 80.0:
            return None

        # BTC makro trend filtresi — engelleme yok, güven düşürülür
        btc_str = btc_macro.get("strength", 0)
        if btc_trend == "bearish" and direction == "long":
            penalty = 25 if btc_str >= 0.8 else 15
            logger.debug(f"{pair}: CRT — BTC makro BEARISH, LONG güven -{penalty}")
        elif btc_trend == "bullish" and direction == "short":
            penalty = 25 if btc_str >= 0.8 else 15
            logger.debug(f"{pair}: CRT — BTC makro BULLISH, SHORT güven -{penalty}")

        # Bias gücü minimum 0.30 — CRT için de zorunlu
        if bias.get("strength", 0) < 0.30:
            logger.debug(f"{pair}: CRT bias gücü düşük ({bias.get('strength',0):.2f}) — atlandı")
            return None

        # Karakter değişimi onaylanmış olmalı
        if not crt_result.get("choch_confirmed"):
            logger.debug(f"{pair}: CRT karakter değişimi onaylanmadı — atlandı")
            return None

        if is_recent_signal_exists(pair, direction_str, hours=12):
            return None

        # ── Seviyeler ────────────────────────────────
        price = candles_4h[-1]["close"]
        atr   = calculate_atr(candles_4h) or (price * 0.02)

        # Swing high/low — fibonacci için
        swings_fib = find_swing_points(candles_4h, window=5)
        s_high_fib = swings_fib["swing_highs"][-1]["price"] if swings_fib["swing_highs"] else None
        s_low_fib  = swings_fib["swing_lows"][-1]["price"]  if swings_fib["swing_lows"]  else None

        entry_min, entry_max, stop_loss, tp1, tp2, tp3 = _calc_levels(direction_str, price, atr, s_high_fib, s_low_fib)

        # CRT manipülasyon seviyesine göre SL ayarla
        manip_price = crt_result.get("manipulation_price")
        if manip_price:
            if direction == "long":  stop_loss = min(stop_loss, manip_price * 0.995)
            else:                    stop_loss = max(stop_loss, manip_price * 1.005)

        risk = abs(price - stop_loss)
        rr   = round(abs(tp2 - price) / risk, 2) if risk > 0 else 2.0

        if rr < 1.3:
            logger.debug(f"{pair}: CRT R/R düşük ({rr}) — atlandı")
            return None

        # CE noktası
        ce_level = crt_result.get("ce_level", 0)
        ce_note  = f"CE Noktası: ${_fmt(ce_level)} | " if ce_level else ""

        # SMT notu
        smt_note = f"\n🔀 SMT Uyumsuzluğu: {smt['type']}" if smt else ""

        # Karakter Değişimi notu
        cc_note = "\n✅ Karakter Değişimi ONAYLANDI" if crt_result.get("choch_confirmed") else "\n⏳ Karakter Değişimi bekleniyor"

        crt_type = crt_result.get("type", "CRT")

        analysis_text = (
            f"💠 A++ CRT SİNYALİ\n\n"
            f"📅 Bias: {direction.upper()} ({bias['zone']}, güç:{bias['strength']:.2f})\n"
            f"🔄 CRT Yapısı: {crt_type}\n"
            f"   Parent High: ${_fmt(crt_result.get('parent_high', 0))}\n"
            f"   Parent Low:  ${_fmt(crt_result.get('parent_low', 0))}\n"
            f"   Manipülasyon: ${_fmt(manip_price)}\n"
            f"{cc_note}\n"
            f"{ce_note}R/R: 1:{rr}\n"
            f"Key Level: {'FVG' if fvgs else ''} {'OB' if obs else ''}\n"
            f"Seans: {session['label']}"
            f"{smt_note}"
        )

        # ── NDOG/NWOG Analizi (sadece bilgi, filtreleme yok) ──────────
        gap_data_crt = detect_ndog_nwog(pair)

        # CRT geçerlilik: 1D+4H = 48 saat
        # Fiyat bazlı iptal — parent candle kırılırsa geçersiz
        if direction_str == "LONG":
            invalidation_price = crt_result.get("parent_low", round(entry_min * 0.97, 8))
        else:
            invalidation_price = crt_result.get("parent_high", round(entry_max * 1.03, 8))

        signal_id = save_signal(
            signal_type="CRT", pair=pair, direction=direction_str,
            entry_min=entry_min, entry_max=entry_max, stop_loss=stop_loss,
            tp1=tp1, tp2=tp2, tp3=tp3, confidence=conf,
            timeframe="1D+4H (A++)", analysis_text=analysis_text, rr_ratio=rr,
            expires_in_hours=48,
            indicators={
                "ndog_count":    len(gap_data_crt.get("ndog", [])),
                "nwog_count":    len(gap_data_crt.get("nwog", [])),
                "nearest_ndog":  gap_data_crt.get("nearest_ndog"),
                "nearest_nwog":  gap_data_crt.get("nearest_nwog"),
                "price_in_ndog": gap_data_crt.get("current_price_in_ndog", False),
                "price_in_nwog": gap_data_crt.get("current_price_in_nwog", False),
            },
        )
        gap_analysis_crt = analyze_gap_vs_signal(
            {"direction": direction_str, "current_price": price}, gap_data_crt
        )
        # boost uygulanmıyor — sadece bilgi

        crt_result_final = {
            "id": signal_id, "type": "CRT", "pair": pair,
            "direction": direction_str, "timeframe": "1D + 4H",
            "entry_min": entry_min, "entry_max": entry_max,
            "stop_loss": stop_loss, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "rr_ratio": rr, "confidence": conf,
            "analysis": analysis_text,
            "current_price": price,
            "created_at": datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
            "bias": bias,
            "crt": crt_result,
            "smt": smt,
            "session": session["label"],
            "has_smt": smt is not None,
            "ndog_info": gap_analysis_crt.get("ndog_info", ""),
            "nwog_info": gap_analysis_crt.get("nwog_info", ""),
            "gap_warnings": gap_analysis_crt.get("warnings", []),
            "gap_boost": gap_analysis_crt.get("boost", 0),
            "expires_in_hours": 48,
            "invalidation_price": invalidation_price,
        }

        # Likidite + manipülasyon analizi
        try:
            crt_result_final["liq_analiz"] = analyze_liquidity_for_signal(crt_result_final)
        except Exception:
            pass

        return crt_result_final

    except Exception as e:
        logger.error(f"CRT sinyal hatası ({pair}): {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
#  SINYAL FORMATLAYICI
# ═══════════════════════════════════════════════════════════════════

def format_signal_message(signal: dict) -> str:
    e      = EMOJI
    dir_em = "📈" if signal["direction"] == "LONG" else "📉"
    pair   = signal["pair"].replace("USDT", "/USDT")
    stars  = "⭐" * min(5, int(signal["confidence"] / 20))
    conf   = signal["confidence"]

    headers = {
        "NORMAL":  "🚀 NORMAL SİNYAL",
        "MSB_FVG": "🎯 MSB+FVG SİNYALİ",
        "CRT":     "🏆 A++ CRT SİNYALİ",
    }
    header = headers.get(signal["type"], "📊 SİNYAL")
    ep = signal.get("current_price", 0)
    tf = signal.get("timeframe", "1h")

    # Bias ve seans
    bias_line = ""
    if signal.get("bias") and signal["bias"].get("zone"):
        bias_line = f"\n📍 Bias: {signal['direction']} ({signal['bias'].get('zone','')}, güç:{signal['bias'].get('strength',0):.2f})"

    sess_line = f"\n🕐 Seans: {signal.get('session', '')}" if signal.get("session") else ""
    kz_line   = f"\n⚡ Kill Zone: {signal['kill_zone']}" if signal.get("kill_zone") else ""
    tgif_line = "\n📅 TGIF — Cuma likiditesi dikkat!" if signal.get("tgif") else ""
    smt_line  = "\n🔀 SMT Uyumsuzluğu: Aktif (Güçlü sinyal!)" if signal.get("has_smt") else ""

    # NDOG/NWOG satırları
    ndog_line = f"\n{signal['ndog_info']}" if signal.get("ndog_info") else ""
    nwog_line = f"\n{signal['nwog_info']}" if signal.get("nwog_info") else ""
    gap_warn_lines = ""  # warnings kaldırıldı — mesaj kısaltıldı
    gap_boost_line = ""

    analysis = signal.get("analysis", "").replace("_", "\\_")

    # Geçerlilik ve iptal bilgisi
    expires_h    = signal.get("expires_in_hours", 8)
    invalidation = signal.get("invalidation_price", 0)
    valid_line   = f"\n⏰ Geçerlilik: {expires_h} saat" if expires_h else ""
    if invalidation:
        inv_dir   = signal.get("direction", "LONG")
        inv_label = "altı" if inv_dir == "LONG" else "üstü"
        invalid_line = f"\n🚫 İptal: ${_fmt(invalidation)} {inv_label} kırılırsa setup geçersiz"
    else:
        invalid_line = ""

    # AI kararlarini uret ve tek mesaja dahil et — 3 AI
    kural_yorum  = _ai_yorum_kural(signal)
    groq_yorum   = _gemini_yorum(signal)
    gemini_yorum = _gemini_google_yorum(signal)

    kural_karar  = _karar_cikart(kural_yorum)
    groq_karar   = _karar_cikart(groq_yorum)
    gemini_karar = _karar_cikart(gemini_yorum)
    kararlar     = [k for k in [kural_karar, groq_karar, gemini_karar] if k]
    ortak        = _ortak_karar(kararlar)

    ayrac = "─" * 32
    ai_blok = (
        f"\n{ayrac}\n"
        f"🤖 **AI KARARI**\n"
        f"{kural_yorum}"
        f"{groq_yorum if groq_yorum else ''}"
        f"{gemini_yorum if gemini_yorum else ''}"
        f"{ortak}"
        f"{_quality_block(signal)}"
    )

    return (
        f"{header} — {pair}\n"
        f"{'─'*32}\n"
        f"{dir_em} Yön: **{signal['direction']}**\n"
        f"🕐 Zaman: {signal.get('created_at','')} (GMT+3)\n"
        f"📊 Timeframe: {tf}\n"
        f"{stars} Güven: **%{conf:.0f}**"
        f"{bias_line}{sess_line}{kz_line}{tgif_line}{smt_line}{ndog_line}{nwog_line}{gap_warn_lines}{gap_boost_line}\n\n"
        f"💰 Güncel Fiyat: ${_fmt(ep)}\n\n"
        f"📍 **GİRİŞ ZONU:**\n"
        f"   ${_fmt(signal['entry_min'])} — ${_fmt(signal['entry_max'])}\n\n"
        f"🎯 **HEDEFLER:**\n"
        f"   TP1: ${_fmt(signal['tp1'])}\n"
        f"   TP2: ${_fmt(signal['tp2'])}\n"
        f"   TP3: ${_fmt(signal['tp3'])}\n\n"
        f"🛑 **STOP LOSS:** ${_fmt(signal['stop_loss'])}\n"
        f"📐 **Risk/Reward:** 1:{signal.get('rr_ratio','N/A')}\n\n"
        f"📊 **ANALİZ:**\n{analysis}\n"
        f"{valid_line}{invalid_line}\n"
        f"{ai_blok}"
    )






def format_ai_message(signal: dict) -> str:
    """
    AI kararları mesajı — Kural AI + Groq + Gemini.
    3 AI uyumluysa güçlü sinyal, çelişiyorsa dikkat.
    """
    pair      = signal["pair"].replace("USDT", "/USDT")
    dir_em    = "📈" if signal["direction"] == "LONG" else "📉"
    direction = signal["direction"]

    kural_yorum  = _ai_yorum_kural(signal)
    groq_yorum   = _gemini_yorum(signal)
    gemini_yorum = _gemini_google_yorum(signal)

    kural_karar  = _karar_cikart(kural_yorum)
    groq_karar   = _karar_cikart(groq_yorum)
    gemini_karar = _karar_cikart(gemini_yorum)
    kararlar     = [k for k in [kural_karar, groq_karar, gemini_karar] if k]
    ortak        = _ortak_karar(kararlar)

    ayrac = "─" * 32
    msg = (
        f"🤖 AI KARARI — {pair}\n"
        f"{ayrac}\n"
        f"{dir_em} Yön: **{direction}**\n\n"
        f"{kural_yorum}"
    )

    if groq_yorum:
        msg += f"\n{groq_yorum}"

    if gemini_yorum:
        msg += f"\n{gemini_yorum}"

    msg += ortak
    msg += _quality_block(signal)

    return msg

def _karar_cikart(yorum: str) -> str:
    """AI yorumundan GİR/BEKLE/ATLA kararını çıkarır."""
    if not yorum:
        return ""
    u = yorum.upper()
    # Önce BEKLE ve ATLA kontrol et, sonra GİR (çakışma önlemi)
    if "KARAR: BEKLE" in u:
        return "BEKLE"
    if "KARAR: ATLA" in u:
        return "ATLA"
    if "KARAR: G" in u:
        return "GİR"
    return ""


def _ortak_karar(kararlar: list) -> str:
    """3 AI kararından ortak mesaj üretir."""
    gir_say   = kararlar.count("GİR")
    atla_say  = kararlar.count("ATLA")
    bekle_say = kararlar.count("BEKLE")
    toplam    = len(kararlar)

    if gir_say == 3:
        return "\n\n🟢🟢🟢 **3 AI DE GİR DEDİ — GÜÇLÜ SİNYAL!**"
    elif gir_say == 2:
        return "\n\n🟢🟢 **2 AI GİR DEDİ — GİREBİLİRSİN**"
    elif atla_say == 3:
        return "\n\n🔴🔴🔴 **3 AI DE ATLA DEDİ — KESİNLİKLE GEÇME!**"
    elif atla_say == 2:
        return "\n\n🔴🔴 **2 AI ATLA DEDİ — GEÇME!**"
    elif bekle_say >= 2:
        return "\n\n🟡🟡 **2 AI BEKLE DEDİ — ZONA GELMESİNİ BEKLE**"
    else:
        return "\n\n🟡 **AI KARARLARI ÇELİŞİYOR — DİKKATLİ OL**"


def _gemini_yorum(signal: dict) -> str:
    """Groq API ile gerçek AI yorumu üretir."""
    import os, requests
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return ""

    try:
        direction  = signal.get("direction", "")
        pair       = signal.get("pair", "")
        price      = signal.get("current_price", 0)
        entry_min  = signal.get("entry_min", 0)
        entry_max  = signal.get("entry_max", 0)
        stop_loss  = signal.get("stop_loss", 0)
        tp1        = signal.get("tp1", 0)
        tp2        = signal.get("tp2", 0)
        tp3        = signal.get("tp3", 0)
        rr         = signal.get("rr_ratio", 0)
        bias       = signal.get("bias", {}) or {}
        bias_str   = bias.get("strength", 0)
        bias_zone  = bias.get("zone", "")
        sig_type   = signal.get("type", "")
        analysis   = signal.get("analysis", "")
        session    = signal.get("session", "")
        timeframe  = signal.get("timeframe", "")
        confidence = signal.get("confidence", 0)

        btc_macro = get_btc_macro_bias()
        btc_trend = btc_macro.get("trend", "neutral")
        btc_str   = btc_macro.get("strength", 0)

        # Fiyat durumu
        if entry_min <= price <= entry_max:
            fiyat_durum = "ZONDA"
        elif (direction == "LONG" and price > entry_max) or (direction == "SHORT" and price < entry_min):
            fiyat_durum = "GEÇTİ"
        else:
            fiyat_durum = "BEKLE"

        system_prompt = """Sen kurumsal para akışını okuyan uzman bir ICT (Inner Circle Trader) kripto analistisin.
Piyasayı kurumsal gözle görürsün: likidite tuzakları, Smart Money hareketi, sweep ve manipülasyon.

ICT TEMEL KURALLARIN:
- Kurumsal para önce likiditesi süpürür (stop hunt), sonra gerçek yöne gider
- LONG: DISCOUNT bölge + alt likidite sweep + BULLISH CRT/MSB
- SHORT: PREMIUM bölge + üst likidite sweep + BEARISH CRT/MSB
- CRT: Manipülasyon mumu parent içinde kalır, iğne likiditesi alır, sonra ters döner
  * BULLISH CRT: aşağı iğne → LONG beklenir (alt stop'ları süpürdü)
  * BEARISH CRT: yukarı iğne → SHORT beklenir (üst stop'ları süpürdü)
- FVG: Kurumsal dengesizlik bölgesi — 3/3 güç idealdir
- MSB STRONG: yapısal kırılım güçlü, WEAK: güvenilmez
- Kill Zone: kurumsal algoritmalar en aktif bu saatlerde çalışır
- Overlap (Londra+NY): en güçlü seans, en güvenilir sinyaller

KARAR MATRİSİ:
GİR:   Fiyat zonda + CRT yönü uyumlu + PREMIUM/DISCOUNT doğru + R/R≥1.5 + bias≥0.40
BEKLE: Fiyat zona %3 içinde + setup güçlü ama henüz tetiklenmedi
ATLA:  Fiyat zonu geçmiş + DISCOUNT'ta SHORT veya PREMIUM'da LONG + CRT yön çelişkisi + MSB WEAK

KRİTİK KURALLAR:
- DISCOUNT'ta SHORT = kurumsal akışa karşı = ATLA
- PREMIUM'da LONG = kurumsal akışa karşı = ATLA  
- CRT yönü sinyal yönüyle çelişiyorsa = ATLA
- Karakter değişimi (ChoCH) onaylanmamışsa = BEKLE
- BTC makro karşı trend = güven düşür, lot küçült
- SMT aktifse = ekstra güç, kurumsal uyumsuzluk teyit

Türkçe yaz. Maksimum 4 satır. Net ve kararlı ol."""

        # Likidite verilerini hazırla
        liq_data  = signal.get("liquidity") or {}
        k_yon     = liq_data.get("kurumsal_yon", "NEUTRAL")
        k_guc     = liq_data.get("yon_guc", "ZAYIF")
        fr_label  = liq_data.get("funding_rate", {}).get("label", "Veri yok")
        ls_label  = liq_data.get("long_short", {}).get("label", "Veri yok")
        oi_label  = liq_data.get("open_interest", {}).get("label", "Veri yok")

        # CRT ve SMT bilgilerini hazırla
        crt_info = signal.get("crt") or {}
        crt_type = crt_info.get("type", "YOK")
        choch    = "ONAYLANDI" if crt_info.get("choch_confirmed") else "BEKLENİYOR"
        smt_info = "AKTİF" if signal.get("has_smt") else "YOK"
        fvg_guc  = "3/3" if "3/3" in signal.get("analysis","") else ("2/3" if "2/3" in signal.get("analysis","") else ("1/3" if "1/3" in signal.get("analysis","") else "?"))
        kz_info  = signal.get("kill_zone") or "YOK"

        prompt = f"""{pair} {direction} sinyali ICT/CRT perspektifinden değerlendir:

Coin:{pair} | Yön:{direction} | TF:{timeframe} | Tip:{sig_type}
Güven:%{confidence} | R/R:1:{rr}
Fiyat:{price} | Zon:{entry_min}-{entry_max} ({fiyat_durum})
SL:{stop_loss} | TP1:{tp1} | TP2:{tp2}
Bias:{bias_zone} güç:{bias_str:.2f} | BTC:{btc_trend}({btc_str:.2f})
Seans:{session} | Kill Zone:{kz_info}
CRT:{crt_type} | ChoCH:{choch} | SMT:{smt_info} | FVG:{fvg_guc}
Bias_1D:{bias_zone} | Bias_1H:{signal.get("indicators", {}).get("ict_zone", "?")} | RSI:{signal.get("indicators", {}).get("rsi", "?")}
Kurumsal:{k_yon}({k_guc}) | Funding:{fr_label}
L/S:{ls_label} | OI:{oi_label}

TAM OLARAK 4 satır yaz, her satır max 6 kelime:
📊 [fiyat/zon durumu]
💡 [ICT/CRT setup kalitesi]
⚠️ [ana risk]
🟢/🟡/🔴 KARAR: GİR/BEKLE/ATLA"""

        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200,
                "temperature": 0.3
            },
            timeout=10
        )

        if resp.status_code == 200:
            text = resp.json()["choices"][0]["message"]["content"].strip()
            # Son satır KARAR satırı — sadece onu göster
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            short = "\n".join(lines[:4])  # max 4 satır
            return f"\n\n🤖 **AI Yorumu:** {short}"
        logger.debug(f"Groq API hatası: {resp.status_code} {resp.text[:100]}")
        return ""
    except Exception as e:
        logger.debug(f"Groq API hatası: {e}")
        return ""


def _gemini_google_yorum(signal: dict) -> str:
    """Google Gemini API ile sinyal yorumu üretir."""
    import os, requests
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return ""

    try:
        direction  = signal.get("direction", "")
        pair       = signal.get("pair", "")
        price      = signal.get("current_price", 0)
        entry_min  = signal.get("entry_min", 0)
        entry_max  = signal.get("entry_max", 0)
        stop_loss  = signal.get("stop_loss", 0)
        tp1        = signal.get("tp1", 0)
        rr         = signal.get("rr_ratio", 0)
        bias       = signal.get("bias", {}) or {}
        bias_zone  = bias.get("zone", "")
        bias_str   = bias.get("strength", 0)
        sig_type   = signal.get("type", "")
        session    = signal.get("session", "")
        confidence = signal.get("confidence", 0)
        timeframe  = signal.get("timeframe", "")

        btc_macro  = get_btc_macro_bias()
        btc_trend  = btc_macro.get("trend", "neutral")
        btc_str    = btc_macro.get("strength", 0)

        crt_info   = signal.get("crt") or {}
        crt_type   = crt_info.get("type", "YOK")
        choch      = "ONAYLANDI" if crt_info.get("choch_confirmed") else "BEKLIYOR"
        smt_info   = "AKTIF" if signal.get("has_smt") else "YOK"
        fvg_guc    = "3/3" if "3/3" in signal.get("analysis","") else ("2/3" if "2/3" in signal.get("analysis","") else "1/3")

        if entry_min <= price <= entry_max:
            fiyat_durum = "ZONDA"
        elif (direction == "LONG" and price > entry_max) or (direction == "SHORT" and price < entry_min):
            fiyat_durum = "GECTI"
        else:
            fiyat_durum = "BEKLE"

        prompt = f"""Sen ICT (Inner Circle Trader) uzmanı bir kripto analistisin.
Kurumsal para akışını, likidite tuzaklarını ve Smart Money hareketlerini analiz edersin.

ICT KURALLARIN:
- LONG: DISCOUNT bolge + alt likidite sweep + BULLISH CRT/MSB
- SHORT: PREMIUM bolge + ust likidite sweep + BEARISH CRT/MSB  
- CRT manipulasyon asagi → LONG, yukari → SHORT
- Fiyat zonu gectiyse ne kadar guclu olursa ATLA
- RSI asiri satimda SHORT acma
- BTC makro karsi trend = risk artisi

KARAR KURALLARI:
GIR: Fiyat zonda + PREMIUM/DISCOUNT dogru + R/R>=1.5 + bias>=0.40 + BTC uyumlu
BEKLE: Fiyat zona %3 icinde + setup guclu
ATLA: Fiyat zonu gecmis + yanlis bolge + CRT celiskisi

{pair} {direction} sinyali:
Fiyat:{price} | Zon:{entry_min}-{entry_max} ({fiyat_durum})
Guvence:%{confidence} | R/R:1:{rr} | TF:{timeframe}
Bias:{bias_zone} guc:{bias_str:.2f} | BTC:{btc_trend}({btc_str:.2f})
Seans:{session} | Tip:{sig_type}
CRT:{crt_type} | ChoCH:{choch} | SMT:{smt_info} | FVG:{fvg_guc}

TAM OLARAK 4 satir yaz:
📊 [fiyat/zon durumu]
💡 [ICT/CRT setup kalitesi]
⚠️ [ana risk]
🟢/🟡/🔴 KARAR: GIR/BEKLE/ATLA"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 200,
                }
            },
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            short = "\n".join(lines[:4])
            return f"\n\n✨ **Gemini:** {short}"

        logger.debug(f"Gemini API hatası: {resp.status_code} {resp.text[:100]}")
        return ""
    except Exception as e:
        logger.debug(f"Gemini API hatası: {e}")
        return ""


def _ai_yorum(signal: dict) -> str:
    """
    Kural tabanlı AI + Groq AI yorumlarını birleştirir.
    İkisi de GİR derse yeşil, çelişirse sarı gösterir.
    """
    # 1. Kural tabanlı karar
    kural_yorum = _ai_yorum_kural(signal)

    # 2. Groq yorumu
    groq_yorum = _gemini_yorum(signal)

    if not groq_yorum:
        return kural_yorum

    # Kural tabanlı kararı çıkar
    kural_karar = ""
    if "KARAR: GİR" in kural_yorum:
        kural_karar = "GİR"
    elif "KARAR: BEKLE" in kural_yorum:
        kural_karar = "BEKLE"
    elif "KARAR: ATLA" in kural_yorum:
        kural_karar = "ATLA"

    # Groq kararını çıkar
    groq_karar = ""
    groq_upper = groq_yorum.upper()
    if "GİR" in groq_upper and "KARAR" in groq_upper:
        groq_karar = "GİR"
    elif "BEKLE" in groq_upper and "KARAR" in groq_upper:
        groq_karar = "BEKLE"
    elif "ATLA" in groq_upper and "KARAR" in groq_upper:
        groq_karar = "ATLA"

    # Ortak karar
    if kural_karar == groq_karar == "GİR":
        ortak = "\n\n🟢🟢 **İKİ AI DE ONAYLADI — GİREBİLİRSİN!**"
    elif kural_karar == groq_karar == "ATLA":
        ortak = "\n\n🔴🔴 **İKİ AI DE ATLA DEDİ — GEÇME!**"
    elif kural_karar == groq_karar == "BEKLE":
        ortak = "\n\n🟡🟡 **İKİ AI DE BEKLE DEDİ — ZONA GELMESİNİ BEKLE**"
    elif "GİR" in [kural_karar, groq_karar]:
        ortak = "\n\n🟡 **AI KARARLARI ÇELİŞİYOR — DİKKATLİ OL**"
    else:
        ortak = ""

    return kural_yorum + groq_yorum + ortak


def _ai_yorum_kural(signal: dict) -> str:
    """
    Kural tabanlı otomatik sinyal yorumu.
    API gerektirmez — sinyal verilerine göre üretir.
    """
    try:
        direction  = signal.get("direction", "")
        price      = float(signal.get("current_price", 0))
        entry_min  = float(signal.get("entry_min", 0))
        entry_max  = float(signal.get("entry_max", 0))
        stop_loss  = float(signal.get("stop_loss", 0))
        tp1        = float(signal.get("tp1", 0))
        rr         = float(signal.get("rr_ratio", 0) or 0)
        bias       = signal.get("bias", {}) or {}
        bias_str   = float(bias.get("strength", 0) or 0)
        sig_type   = signal.get("type", "NORMAL")
        analysis   = signal.get("analysis", "")
        session    = signal.get("session", "")

        lines = ["\n🤖 **AI Değerlendirme:**"]
        karar = ""

        # 0. RSI aşırı bölge kontrolü — önce bunu geç
        rsi_val_k = signal.get("indicators", {}).get("rsi", 50)
        try:
            rsi_val_k = float(rsi_val_k or 50)
            if rsi_val_k < 30 and direction == "SHORT":
                lines.append("🚨 RSI aşırı satılmış (<30) — SHORT bounce riski!")
                karar = "ATLA"
            elif rsi_val_k > 70 and direction == "LONG":
                lines.append("🚨 RSI aşırı alınmış (>70) — LONG düzeltme riski!")
                karar = "ATLA"
            elif rsi_val_k < 40 and direction == "SHORT":
                lines.append(f"⚠️ RSI düşük ({rsi_val_k:.0f}) — SHORT için zayıf bölge")
            elif rsi_val_k > 60 and direction == "LONG":
                lines.append(f"⚠️ RSI yüksek ({rsi_val_k:.0f}) — LONG için zayıf bölge")
        except:
            pass

        # 1. Fiyat pozisyonu
        if entry_min <= price <= entry_max:
            lines.append("✅ Fiyat giriş zonunda")
            karar = "GİR"
        elif direction == "LONG" and price < entry_min:
            fark_pct = (entry_min - price) / price * 100
            lines.append(f"⏳ Fiyat zonun {fark_pct:.1f}% altında — yukarı çekilme bekle")
            karar = "BEKLE"
        elif direction == "SHORT" and price > entry_max:
            fark_pct = (price - entry_max) / price * 100
            lines.append(f"⏳ Fiyat zonun {fark_pct:.1f}% üstünde — aşağı çekilme bekle")
            karar = "BEKLE"
        elif direction == "LONG" and price > entry_max:
            fark_pct = (price - entry_max) / price * 100
            lines.append(f"⚠️ Fiyat zonu {fark_pct:.1f}% geçti — geç kalındı")
            karar = "ATLA"
        elif direction == "SHORT" and price < entry_min:
            fark_pct = (entry_min - price) / price * 100
            lines.append(f"⚠️ Fiyat zonu {fark_pct:.1f}% geçti — geç kalındı")
            karar = "ATLA"

        # 2. MSB gücü
        if "STRONG" in analysis:
            lines.append("💪 MSB güçlü kırılım — yapısal destek var")
        elif "MODERATE" in analysis:
            lines.append("📊 MSB orta kırılım — kabul edilebilir")
        elif "WEAK" in analysis:
            lines.append("⚠️ MSB zayıf — dikkatli ol")

        # 3. Bias gücü
        if bias_str >= 0.7:
            lines.append("🔥 Bias çok güçlü — yön net")
        elif bias_str >= 0.5:
            lines.append("✅ Bias güçlü")
        elif bias_str >= 0.35:
            lines.append("⚠️ Bias orta — stop sıkı tut")
        else:
            lines.append("🚨 Bias zayıf — pozisyon küçük aç")

        # 4. R/R yorumu
        if rr >= 3:
            lines.append(f"🏆 Mükemmel R/R (1:{rr}) — tam lot girilebilir")
        elif rr >= 2:
            lines.append(f"✅ İyi R/R (1:{rr})")
        elif rr >= 1.5:
            lines.append(f"📊 Kabul edilebilir R/R (1:{rr})")
        else:
            lines.append(f"⚠️ Düşük R/R (1:{rr}) — yarım lot düşün")

        # 5. Seans
        if "Overlap" in session:
            lines.append("⚡ Overlap seansı — en güçlü zaman")
        elif "Londra" in session:
            lines.append("🇬🇧 Londra seansı — aktif piyasa")
        elif "Pre-Market" in session:
            lines.append("🌅 Pre-Market — biraz bekleyebilirsin")

        # 6. Sinyal tipi
        if sig_type == "CRT":
            lines.append("💎 CRT yapısı — A++ setup")
        elif sig_type == "MSB_FVG":
            lines.append("🎯 MSB+FVG — yapısal sinyal")

        # ── ICT/CRT KATMANI ─────────────────────────────────────────

        # 8. CRT yapı detayı
        crt = signal.get("crt") or {}
        if crt.get("found"):
            crt_type = crt.get("type", "")
            choch    = crt.get("choch_confirmed", False)
            if crt_type == "BULLISH_CRT" and direction == "LONG":
                lines.append("✅ CRT LONG yönü teyit — manipülasyon aşağı, gerçek yön yukarı")
            elif crt_type == "BEARISH_CRT" and direction == "SHORT":
                lines.append("✅ CRT SHORT yönü teyit — manipülasyon yukarı, gerçek yön aşağı")
            elif crt_type and direction:
                lines.append("⚠️ CRT yönü sinyal yönüyle çelişiyor — dikkatli ol")
                if karar == "GİR":
                    karar = "BEKLE"
            if choch:
                lines.append("✅ Karakter değişimi onaylandı — yapı güçlü")
            else:
                lines.append("⏳ Karakter değişimi bekleniyor — erken giriş riski")

        # 9. FVG kalitesi
        analysis_txt = signal.get("analysis", "")
        if "3/3" in analysis_txt:
            lines.append("💪 FVG 3/3 güç — ideal giriş zonu")
        elif "2/3" in analysis_txt:
            lines.append("📊 FVG 2/3 güç — kabul edilebilir")
        elif "1/3" in analysis_txt:
            lines.append("⚠️ FVG 1/3 güç — zayıf setup")
            if karar == "GİR":
                karar = "BEKLE"

        # 10. SMT uyumsuzluğu
        if signal.get("has_smt"):
            lines.append("🔀 SMT aktif — kurumsal uyumsuzluk tespit edildi (güçlü sinyal)")

        # 11. NDOG/NWOG mıknatıs
        ndog = signal.get("ndog_info", "")
        nwog = signal.get("nwog_info", "")
        if ndog:
            if "uyumlu" in ndog.lower():
                lines.append(f"📐 {ndog}")
            elif "karşı" in ndog.lower() or "dikkat" in ndog.lower():
                lines.append(f"⚠️ {ndog}")
        if nwog:
            if "uyumlu" in nwog.lower():
                lines.append(f"📅 {nwog}")

        # 12. Kill Zone
        if signal.get("kill_zone"):
            lines.append(f"⚡ Kill Zone aktif ({signal['kill_zone']}) — zamanlama ideal")

        # 14. Likidite + Manipülasyon Analizi
        liq_analiz = signal.get("liq_analiz") or {}
        if liq_analiz:
            manip_score = liq_analiz.get("manip_score", 0)
            liq_karar   = liq_analiz.get("karar", "BEKLE")
            liq_ozet    = liq_analiz.get("özet", "")

            if manip_score >= 60:
                lines.append(f"🔴 Manipülasyon riski YÜKSEK ({manip_score}/100) — {liq_ozet}")
                karar = "ATLA"
            elif manip_score >= 30:
                lines.append(f"🟡 Manipülasyon riski ORTA ({manip_score}/100) — dikkatli ol")
                if karar == "GİR":
                    karar = "BEKLE"
            else:
                lines.append(f"🟢 Manipülasyon riski düşük ({manip_score}/100)")

            liq_liq = liq_analiz.get("liq", {})
            if liq_liq.get("signal") != "NEUTRAL" and liq_liq.get("label") != "Veri yok":
                lines.append(f"💧 {liq_liq.get('label', '')}")

        # 15. Kurumsal likidite verisi (Funding/L-S/OI)
        liq = signal.get("liquidity") or {}
        kurumsal_yon = liq.get("kurumsal_yon", "NEUTRAL")
        yon_guc      = liq.get("yon_guc", "ZAYIF")
        fr           = liq.get("funding_rate", {})
        ls           = liq.get("long_short", {})
        oi           = liq.get("open_interest", {})

        if kurumsal_yon != "NEUTRAL":
            if kurumsal_yon == direction and yon_guc == "GÜÇLÜ":
                lines.append(f"🏦 Kurumsal yön {direction} uyumlu — güçlü teyit")
            elif kurumsal_yon == direction and yon_guc == "ORTA":
                lines.append(f"🏦 Kurumsal yön {direction} uyumlu — orta teyit")
            elif kurumsal_yon != direction and yon_guc == "GÜÇLÜ":
                lines.append(f"⚠️ Kurumsal yön {kurumsal_yon} — sinyal yönüyle çelişiyor!")
                if karar == "GİR":
                    karar = "BEKLE"

        if fr.get("signal") in ("SHORT_AVANTAJ", "LONG_AVANTAJ"):
            lines.append(f"💰 Funding: {fr.get('label', '')}")
        if ls.get("signal") in ("SHORT_AVANTAJ", "LONG_AVANTAJ"):
            lines.append(f"👥 L/S Oran: {ls.get('label', '')}")
        if oi.get("signal") in ("STRONG", "WEAK"):
            lines.append(f"📊 OI: {oi.get('label', '')}")

        # 13. Premium/Discount doğrulama
        bias_zone = bias.get("zone", "")
        if direction == "SHORT" and bias_zone == "PREMIUM":
            lines.append("✅ PREMIUM bölgede SHORT — ICT kuralına uygun")
        elif direction == "LONG" and bias_zone == "DISCOUNT":
            lines.append("✅ DISCOUNT bölgede LONG — ICT kuralına uygun")
        elif direction == "SHORT" and bias_zone == "DISCOUNT":
            lines.append("🚨 DISCOUNT bölgede SHORT — ICT kuralına AYKIRI")
            karar = "ATLA"
        elif direction == "LONG" and bias_zone == "PREMIUM":
            lines.append("🚨 PREMIUM bölgede LONG — ICT kuralına AYKIRI")
            karar = "ATLA"

        # 7. BTC makro
        try:
            btc_m = get_btc_macro_bias()
            btc_t = btc_m.get("trend", "neutral")
            btc_s = btc_m.get("strength", 0)
            if btc_t == "bearish":
                lines.append(f"📉 BTC makro BEARISH (güç:{btc_s:.2f}) — SHORT uyumlu" if direction == "SHORT"
                             else f"⚠️ BTC makro BEARISH — LONG riskli")
            elif btc_t == "bullish":
                lines.append(f"📈 BTC makro BULLISH (güç:{btc_s:.2f}) — LONG uyumlu" if direction == "LONG"
                             else f"⚠️ BTC makro BULLISH — SHORT riskli")
        except:
            pass

        # 8. Karar
        karar_emoji = {"GİR": "🟢", "BEKLE": "🟡", "ATLA": "🔴"}.get(karar, "⚪")
        if karar:
            lines.append(f"\n{karar_emoji} **KARAR: {karar}**")
            if karar == "GİR":
                sl_pct = abs(price - stop_loss) / price * 100
                lines.append(f"   Stop: ${_fmt(stop_loss)} (%{sl_pct:.1f} risk)")
                lines.append(f"   TP1 hedef: ${_fmt(tp1)}")
            elif karar == "BEKLE":
                lines.append(f"   Giriş zonu: ${_fmt(entry_min)} — ${_fmt(entry_max)}")

        return "\n".join(lines)

    except Exception as e:
        return ""

def _quality_block(signal: dict) -> str:
    """Mesaj sonuna kalite skoru bloğu ekler."""
    try:
        from utils.chart_generator import format_quality_block
        return format_quality_block(signal)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════
#  TOPLU TARAYICI
# ═══════════════════════════════════════════════════════════════════

def scan_all_pairs_for_signals(signal_type: str = "NORMAL") -> list:
    """
    Tüm desteklenen coinleri PARALEL tarar (ThreadPoolExecutor).
    Sırayla değil aynı anda — tarama süresi ~5x azalır.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if is_monday() and signal_type != "CRT":
        logger.info(f"Pazartesi — Fog of War, {signal_type} taraması atlandı")
        return []

    STABLECOIN_BLACKLIST = {
        "USDCUSDT", "FDUSDUSDT", "PAXGUSDT", "USD1USDT", "BUSDUSDT",
        "TUSDUSDT", "USDPUSDT",  "DAIUSDT",  "USDEUSDT", "RLUSDUSDT",
        "EULUSDT",  "XUSDUSDT",  "BFUSDUSDT", "EURUSDT",
    }

    tarama_listesi = [p for p in SUPPORTED_PAIRS if p not in STABLECOIN_BLACKLIST]
    logger.info(f"🔍 [{signal_type}] {len(tarama_listesi)} coin paralel taranıyor...")

    found = []

    # NORMAL ve MSB_FVG için çoklu TF tarama
    if signal_type in ("NORMAL", "MSB_FVG"):
        if signal_type == "NORMAL":
            timeframes = ["1h", "4h", "15m"]
        else:  # MSB_FVG
            timeframes = ["4h", "1h", "15m"]

        gen_fn = generate_normal_signal if signal_type == "NORMAL" else generate_msb_fvg_signal

        for tf in timeframes:
            logger.info(f"🔍 [{signal_type}] {tf.upper()} taranıyor...")
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(gen_fn, pair, tf): pair for pair in tarama_listesi}
                for future in as_completed(futures):
                    pair = futures[future]
                    try:
                        sig = future.result(timeout=15)
                        if sig:
                            found.append(sig)
                            logger.info(
                                f"✅ {signal_type} [{tf.upper()}]: {pair} "
                                f"{sig.get('direction','?')} "
                                f"%{sig.get('confidence', 0):.0f}"
                            )
                    except Exception as e:
                        logger.debug(f"Tarama hatası {pair}: {e}")
        return found

    gen = {
        "CRT": generate_crt_signal,
    }.get(signal_type, generate_normal_signal)

    # CRT daha ağır, 4 thread yeterli
    max_workers = 4

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(gen, pair): pair for pair in tarama_listesi}
        for future in as_completed(futures):
            pair = futures[future]
            try:
                sig = future.result(timeout=15)
                if sig:
                    found.append(sig)
                    logger.info(
                        f"✅ {signal_type}: {pair} "
                        f"{sig.get('direction','?')} "
                        f"%{sig.get('confidence', 0):.0f}"
                    )
            except Exception as e:
                logger.debug(f"Tarama hatası {pair}: {e}")

    logger.info(f"📊 [{signal_type}] Tarama bitti: {len(found)} sinyal bulundu")
    return found
