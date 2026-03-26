"""
bot4/utils/helpers.py
Egitim versiyonu — tum seans, zaman ve hesaplama yardimcilari.

YENI EKLENENLER:
  - get_session_quality(): 0-3 skor (Overlap=3, KZ=2, LDN/NY=1, Asya=0)
  - is_overlap_session(): Londra+NY overlap (15:30-19:00 TR)
  - is_spooling_window(): Spooling saatleri (15:30/16:30/17:00 TR)
  - check_judas_swing(): 1M verisinden Judas Swing tespiti
  - calculate_premium_discount(): fib_62/705/79 eklendi
"""

from datetime import datetime, timezone, time as dtime


# ─── KILL ZONE TANIMLARI ─────────────────────────────────────────────────────

KILL_ZONES = [
    {"name": "Londra Acilis KZ",   "start": "10:00", "end": "12:00"},
    {"name": "NY 8:30 Spooling",   "start": "15:25", "end": "15:45"},
    {"name": "NY Acilis KZ",       "start": "15:30", "end": "17:30"},
    {"name": "NY 9:30 Spooling",   "start": "16:25", "end": "16:45"},
    {"name": "NY 10:00 Spooling",  "start": "16:55", "end": "17:15"},
    {"name": "NY Kapanis KZ",      "start": "20:00", "end": "22:00"},
]

SPOOLING_WINDOWS = [
    {"name": "15:30 Spooling", "start": "15:25", "end": "15:45"},
    {"name": "16:30 Spooling", "start": "16:25", "end": "16:45"},
    {"name": "17:00 Spooling", "start": "16:55", "end": "17:15"},
]

# Seans saatleri (TR = UTC+3)
ASYA_SESSION    = {"start": 1,    "end": 10}
LONDON_SESSION  = {"start": 10,   "end": 19}
NY_SESSION      = {"start": 15.5, "end": 22}
OVERLAP_SESSION = {"start": 15.5, "end": 19}   # Londra+NY


def is_kill_zone(now=None) -> bool:
    if now is None:
        now = datetime.now()
    ct = now.strftime("%H:%M")
    return any(z["start"] <= ct <= z["end"] for z in KILL_ZONES)


def get_kill_zone_name(now=None):
    if now is None:
        now = datetime.now()
    ct = now.strftime("%H:%M")
    for z in KILL_ZONES:
        if z["start"] <= ct <= z["end"]:
            return z["name"]
    return None


def get_current_session(now=None) -> str:
    if now is None:
        now = datetime.now()
    h = now.hour + now.minute / 60.0
    if OVERLAP_SESSION["start"] <= h < OVERLAP_SESSION["end"]:
        return "OVERLAP"
    if LONDON_SESSION["start"] <= h < LONDON_SESSION["end"]:
        return "LONDRA"
    if NY_SESSION["start"] <= h < NY_SESSION["end"]:
        return "NEW_YORK"
    if ASYA_SESSION["start"] <= h < ASYA_SESSION["end"]:
        return "ASYA"
    return "KAPALI"


def get_session_quality(now=None) -> int:
    """
    Egitim: Seans kalite skoru.
    3 = Overlap (en guclu)
    2 = Kill Zone
    1 = Londra / NY
    0 = Asya / Kapali (islem yapma!)
    """
    if now is None:
        now = datetime.now()
    h  = now.hour + now.minute / 60.0
    kz = is_kill_zone(now)

    if OVERLAP_SESSION["start"] <= h < OVERLAP_SESSION["end"]:
        return 3
    if kz:
        return 2
    if (LONDON_SESSION["start"] <= h < LONDON_SESSION["end"] or
            NY_SESSION["start"] <= h < NY_SESSION["end"]):
        return 1
    return 0


def is_overlap_session(now=None) -> bool:
    """Londra + NY overlap mi? (15:30-19:00 TR) — en guclu seans."""
    if now is None:
        now = datetime.now()
    h = now.hour + now.minute / 60.0
    return OVERLAP_SESSION["start"] <= h < OVERLAP_SESSION["end"]


def is_spooling_window(now=None) -> tuple:
    """Spooling penceresi mi? (15:30 / 16:30 / 17:00 TR)"""
    if now is None:
        now = datetime.now()
    ct = now.strftime("%H:%M")
    for w in SPOOLING_WINDOWS:
        if w["start"] <= ct <= w["end"]:
            return True, w["name"]
    return False, None


def is_monday(now=None) -> bool:
    """Pazartesi = Fog of War. Islem yapma."""
    if now is None:
        now = datetime.now()
    return now.weekday() == 0


def is_friday_tgif(now=None) -> bool:
    """Cuma = TGIF. Kapanisa dogru manipulasyon var."""
    if now is None:
        now = datetime.now()
    return now.weekday() == 4


def calculate_premium_discount(price: float, swing_high: float, swing_low: float) -> dict:
    """
    Egitim: Fibo 0.5 ile Premium/Discount belirleme.
    Ayrica OTE bantlari (62/70.5/79) hesaplanir.
    """
    if swing_high <= swing_low:
        return {
            'zone': 'NEUTRAL', 'strength': 0.0,
            'fib_50': price, 'is_premium': False,
        }
    rng    = swing_high - swing_low
    fib_50 = swing_low + rng * 0.5

    if price > fib_50:
        zone     = 'PREMIUM'
        strength = (price - fib_50) / (swing_high - fib_50) if (swing_high - fib_50) > 0 else 0
    else:
        zone     = 'DISCOUNT'
        strength = (fib_50 - price) / (fib_50 - swing_low) if (fib_50 - swing_low) > 0 else 0

    return {
        'zone':       zone,
        'strength':   round(min(float(strength), 1.0), 3),
        'fib_50':     fib_50,
        'fib_62':     swing_high - rng * 0.618,
        'fib_705':    swing_high - rng * 0.705,
        'fib_79':     swing_high - rng * 0.790,
        'fib_886':    swing_high - rng * 0.886,
        'is_premium': price > fib_50,
    }


def calculate_rr_ratio(entry: float, stop_loss: float, take_profit: float) -> float:
    risk   = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def check_judas_swing(df_1m, direction: str) -> dict:
    """
    Egitim: Judas Swing = Asya range sweep + Londra geri donus.
    direction: 'long' veya 'short'
    Returns: {'aligned': bool, 'sweep': float, 'real_direction': str}
    """
    if df_1m is None or len(df_1m) < 10:
        return None
    try:
        asya_df = df_1m.between_time('01:00', '10:00')
        kz_df   = df_1m.between_time('10:00', '11:30')
        if asya_df.empty or kz_df.empty:
            return None

        asya_dip   = asya_df['low'].min()
        asya_tepe  = asya_df['high'].max()
        tol        = 0.001

        # Alt sweep + geri donus = LONG sinyali
        if kz_df['low'].min() < asya_dip * (1 - tol):
            if kz_df['close'].iloc[-1] > asya_dip:
                return {'aligned': direction == 'long', 'real_direction': 'long',
                        'sweep': kz_df['low'].min(), 'type': 'ASAGI_ALDATMA'}

        # Ust sweep + geri donus = SHORT sinyali
        if kz_df['high'].max() > asya_tepe * (1 + tol):
            if kz_df['close'].iloc[-1] < asya_tepe:
                return {'aligned': direction == 'short', 'real_direction': 'short',
                        'sweep': kz_df['high'].max(), 'type': 'YUKARI_ALDATMA'}
    except:
        pass
    return None


def format_price(price: float) -> str:
    try:
        if price >= 1000:    return f"${price:,.2f}"
        elif price >= 1:     return f"${price:.4f}"
        elif price >= 0.0001: return f"${price:.6f}"
        else:                 return f"${price:.8f}"
    except:
        return f"${price}"
