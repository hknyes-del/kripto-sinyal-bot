"""
Market Structure analizi - Geliştirilmiş versiyon
MSB (Market Structure Break), BoS (Break of Structure), ChoCH
1H ve 15M periyotlarda kullanılır
"""

import pandas as pd
import numpy as np


def find_swing_points(data, lookback=3):
    """
    Swing high ve swing low noktalarını bul
    """
    highs = data['high'].values
    lows = data['low'].values
    indices = list(range(len(data)))

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(data) - lookback):
        # Swing High
        is_swing_high = all(
            highs[i] >= highs[i - j] for j in range(1, lookback + 1)
        ) and all(
            highs[i] >= highs[i + j] for j in range(1, lookback + 1)
        )

        if is_swing_high:
            swing_highs.append({
                'price': float(highs[i]),
                'index': i,
                'time': data.index[i]
            })

        # Swing Low
        is_swing_low = all(
            lows[i] <= lows[i - j] for j in range(1, lookback + 1)
        ) and all(
            lows[i] <= lows[i + j] for j in range(1, lookback + 1)
        )

        if is_swing_low:
            swing_lows.append({
                'price': float(lows[i]),
                'index': i,
                'time': data.index[i]
            })

    return swing_highs, swing_lows


def detect_msb(data, bias, lookback=3):
    """
    Market Structure Break (MSB) tespiti
    Bias yönüne uygun MSB aranır

    Short bias → Bearish MSB: Yükselen trendin dip kırılımı
    Long bias  → Bullish MSB: Düşen trendin tepe kırılımı
    """
    swing_highs, swing_lows = find_swing_points(data, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    current_close = float(data['close'].iloc[-1])
    last_time = data.index[-1]

    if bias == 'short':
        # Düşüş yapısı: Son dip, bir önceki dibi kırdı mı?
        last_hl = swing_lows[-2]['price']
        recent_low = swing_lows[-1]['price']

        if recent_low < last_hl:
            return {
                'type': 'BEARISH_MSB',
                'direction': 'short',
                'broken_level': float(last_hl),
                'price': current_close,
                'swing_high': swing_highs[-1]['price'],
                'swing_low': float(recent_low),
                'index': swing_lows[-1]['index'],
                'time': swing_lows[-1]['time']
            }

    elif bias == 'long':
        # Yükseliş yapısı: Son tepe, bir önceki tepeyi kırdı mı?
        last_lh = swing_highs[-2]['price']
        recent_high = swing_highs[-1]['price']

        if recent_high > last_lh:
            return {
                'type': 'BULLISH_MSB',
                'direction': 'long',
                'broken_level': float(last_lh),
                'price': current_close,
                'swing_high': float(recent_high),
                'swing_low': swing_lows[-1]['price'],
                'index': swing_highs[-1]['index'],
                'time': swing_highs[-1]['time']
            }

    return None


def detect_bos(data, direction, lookback=3):
    """
    Break of Structure (BoS) – Trend devamı kırılımı
    Trendin devam ettiğini doğrular
    """
    swing_highs, swing_lows = find_swing_points(data, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None

    if direction == 'long':
        # Yükseliş: Her tepe bir öncekinden yüksek
        if swing_highs[-1]['price'] > swing_highs[-2]['price']:
            return {
                'type': 'BULLISH_BOS',
                'broken_level': swing_highs[-2]['price'],
                'new_high': swing_highs[-1]['price'],
                'time': swing_highs[-1]['time']
            }

    elif direction == 'short':
        # Düşüş: Her dip bir öncekinden düşük
        if swing_lows[-1]['price'] < swing_lows[-2]['price']:
            return {
                'type': 'BEARISH_BOS',
                'broken_level': swing_lows[-2]['price'],
                'new_low': swing_lows[-1]['price'],
                'time': swing_lows[-1]['time']
            }

    return None


def determine_trend(data, lookback=5):
    """
    Genel trend yönünü belirle (swing high/low analizi)
    Döndürür: 'bullish', 'bearish', 'ranging'
    """
    swing_highs, swing_lows = find_swing_points(data, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'ranging'

    # Son 2 tepe ve dip
    hh = swing_highs[-1]['price'] > swing_highs[-2]['price']
    hl = swing_lows[-1]['price'] > swing_lows[-2]['price']
    ll = swing_lows[-1]['price'] < swing_lows[-2]['price']
    lh = swing_highs[-1]['price'] < swing_highs[-2]['price']

    if hh and hl:
        return 'bullish'
    elif ll and lh:
        return 'bearish'
    else:
        return 'ranging'