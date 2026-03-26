"""
CRT (Candle Range Theory) Tespiti
ChoCH (Change of Character) + Manipülasyon + Re-test yapısı
1D ve 4H periyotlarda aranır
"""

import pandas as pd
import numpy as np


def find_swing_highs_lows(data, lookback=3):
    """
    Swing high ve swing low noktalarını bul
    Daha hassas tespit için lookback=3
    """
    highs = data['high'].values
    lows = data['low'].values

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(data) - lookback):
        # Swing High: sol ve sağ taraftan daha yüksek
        if all(highs[i] >= highs[i - j] for j in range(1, lookback + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, lookback + 1)):
            swing_highs.append({
                'price': highs[i],
                'index': i,
                'time': data.index[i]
            })

        # Swing Low: sol ve sağ taraftan daha düşük
        if all(lows[i] <= lows[i - j] for j in range(1, lookback + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, lookback + 1)):
            swing_lows.append({
                'price': lows[i],
                'index': i,
                'time': data.index[i]
            })

    return swing_highs, swing_lows


def detect_choch(data, lookback=3):
    """
    ChoCH (Change of Character) tespiti
    Düşen trend: HH ve HL yapısının LL yapmasıyla kırılım (Bearish ChoCH)
    Yükselen trend: LL ve LH yapısının HH yapmasıyla kırılım (Bullish ChoCH)
    """
    swing_highs, swing_lows = find_swing_highs_lows(data, lookback)

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return None

    # Son 3 swing high ve low
    last_highs = swing_highs[-3:]
    last_lows = swing_lows[-3:]

    result = None

    # ---- Bearish ChoCH: Yükseliş → Düşüş ----
    # HH ve HL yapısı var mı?
    if last_highs[-1]['price'] > last_highs[-2]['price']:  # HH
        # Son low bir önceki low'un altına kırdı mı? (LL)
        if len(last_lows) >= 2 and last_lows[-1]['price'] < last_lows[-2]['price']:
            result = {
                'type': 'BEARISH_CHOCH',
                'broken_level': last_lows[-2]['price'],
                'swing_high': last_highs[-1]['price'],
                'swing_low': last_lows[-1]['price'],
                'time': last_lows[-1]['time'],
                'index': last_lows[-1]['index']
            }

    # ---- Bullish ChoCH: Düşüş → Yükseliş ----
    # LL ve LH yapısı var mı?
    if last_lows[-1]['price'] < last_lows[-2]['price']:  # LL
        # Son high bir önceki high'ın üzerine çıktı mı? (HH)
        if len(last_highs) >= 2 and last_highs[-1]['price'] > last_highs[-2]['price']:
            result = {
                'type': 'BULLISH_CHOCH',
                'broken_level': last_highs[-2]['price'],
                'swing_high': last_highs[-1]['price'],
                'swing_low': last_lows[-1]['price'],
                'time': last_highs[-1]['time'],
                'index': last_highs[-1]['index']
            }

    return result


def detect_manipulation(data, choch, lookback=5):
    """
    Manipülasyon tespiti
    ChoCH sonrasında oluşan swing high/low'un alınması
    Örnek: ChoCH bearish ise → son tepe alınması manipülasyon
    """
    if choch is None:
        return None

    close = data['close'].values
    high = data['high'].values
    low = data['low'].values

    choch_idx = choch['index']

    if choch_idx + lookback >= len(data):
        return None

    # ChoCH sonrası mumları analiz et
    post_choch = data.iloc[choch_idx:]

    if choch['type'] == 'BEARISH_CHOCH':
        # Bearish: Fiyat ChoCH sonrası yukarı manipülasyon (son tepe alınır)
        swing_high_level = choch['swing_high']
        recent_high = post_choch['high'].max()

        if recent_high > swing_high_level:
            manip_idx = post_choch['high'].idxmax()
            return {
                'type': 'BEARISH_MANIPULATION',
                'level_taken': float(swing_high_level),
                'manipulation_high': float(recent_high),
                'time': manip_idx,
                'direction': 'bearish'
            }

    elif choch['type'] == 'BULLISH_CHOCH':
        # Bullish: Fiyat ChoCH sonrası aşağı manipülasyon (son dip alınır)
        swing_low_level = choch['swing_low']
        recent_low = post_choch['low'].min()

        if recent_low < swing_low_level:
            manip_idx = post_choch['low'].idxmin()
            return {
                'type': 'BULLISH_MANIPULATION',
                'level_taken': float(swing_low_level),
                'manipulation_low': float(recent_low),
                'time': manip_idx,
                'direction': 'bullish'
            }

    return None


def detect_crt(data, direction=None, lookback=3):
    """
    Tam CRT yapısı tespiti:
    1. ChoCH tespit et
    2. Manipülasyon tespit et
    3. Re-test beklenir (current bar)

    Döndürür: CRT sinyali dict veya None
    """
    if len(data) < 30:
        return None

    # ChoCH bul
    choch = detect_choch(data, lookback)
    if choch is None:
        return None

    # Yön filtresi
    if direction:
        if direction == 'short' and choch['type'] != 'BEARISH_CHOCH':
            return None
        if direction == 'long' and choch['type'] != 'BULLISH_CHOCH':
            return None

    # Manipülasyon bul
    manip = detect_manipulation(data, choch)
    if manip is None:
        return None

    # Re-test kontrolü: Güncel fiyat manipülasyon bölgesine yakın mı?
    current_price = data['close'].iloc[-1]
    manip_level = manip.get('manipulation_high') or manip.get('manipulation_low')

    retest_tolerance = 0.02  # %2 tolerans
    is_retesting = abs(current_price - manip_level) / manip_level < retest_tolerance

    crt_type = choch['type'].split('_')[0]  # 'BEARISH' veya 'BULLISH'

    return {
        'type': f'{crt_type}_CRT',
        'choch': choch,
        'manipulation': manip,
        'is_retesting': is_retesting,
        'swing_high': choch['swing_high'],
        'swing_low': choch['swing_low'],
        'direction': 'short' if crt_type == 'BEARISH' else 'long',
        'current_price': float(current_price),
        'strength': _calculate_crt_strength(choch, manip, is_retesting)
    }


def _calculate_crt_strength(choch, manip, is_retesting):
    """
    CRT güç skoru (0-3)
    """
    score = 0
    if choch is not None:
        score += 1
    if manip is not None:
        score += 1
    if is_retesting:
        score += 1
    return score
