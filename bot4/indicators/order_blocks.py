"""
Order Block (Emir Bloğu) ve Breaker Block tespiti
ICT Metodolojisi
"""

import pandas as pd
import numpy as np
from indicators.market_structure import find_swing_points


def find_order_blocks(data, direction, lookback=50):
    """
    Order Block bul
    direction: 'long' için bullish OB, 'short' için bearish OB

    Bullish OB: Düşüşten önceki son satıcılı (kırmızı) mum
    Bearish OB: Yükselişten önceki son alıcılı (yeşil) mum
    """
    if len(data) < 10:
        return []

    order_blocks = []
    n = min(len(data), lookback)
    subset = data.tail(n).copy()
    close = subset['close'].values
    open_ = subset['open'].values
    high = subset['high'].values
    low = subset['low'].values

    for i in range(1, len(subset) - 2):
        if direction == 'long':
            # Bullish OB: Mum kırmızı (satıcılı) ve ardından güçlü yükseliş gelmiş
            is_bearish_candle = close[i] < open_[i]
            next_is_bullish = close[i + 1] > open_[i + 1]
            impulse_up = close[i + 1] > high[i]  # Ertesi mum OB'nin üzerine kapatıyor

            if is_bearish_candle and next_is_bullish and impulse_up:
                order_blocks.append({
                    'type': 'BULLISH_OB',
                    'top': float(open_[i]),    # OB'nin üst sınırı (mum açılışı)
                    'bottom': float(close[i]),  # OB'nin alt sınırı (mum kapanışı)
                    'high': float(high[i]),
                    'low': float(low[i]),
                    'midpoint': float((open_[i] + close[i]) / 2),
                    'index': i,
                    'time': subset.index[i],
                    'is_mitigated': False  # Henüz ziyaret edilmedi
                })

        elif direction == 'short':
            # Bearish OB: Mum yeşil (alıcılı) ve ardından güçlü düşüş gelmiş
            is_bullish_candle = close[i] > open_[i]
            next_is_bearish = close[i + 1] < open_[i + 1]
            impulse_down = close[i + 1] < low[i]  # Ertesi mum OB'nin altına kapatıyor

            if is_bullish_candle and next_is_bearish and impulse_down:
                order_blocks.append({
                    'type': 'BEARISH_OB',
                    'top': float(close[i]),    # OB'nin üst sınırı (mum kapanışı)
                    'bottom': float(open_[i]),  # OB'nin alt sınırı (mum açılışı)
                    'high': float(high[i]),
                    'low': float(low[i]),
                    'midpoint': float((open_[i] + close[i]) / 2),
                    'index': i,
                    'time': subset.index[i],
                    'is_mitigated': False
                })

    # Güncel fiyata en yakın ve henüz ziyaret edilmemiş OB'yi döndür
    current_price = float(data['close'].iloc[-1])

    # Ziyaret edilmiş OB'leri işaretle
    for ob in order_blocks:
        if direction == 'long' and current_price <= ob['top']:
            ob['is_mitigated'] = True
        elif direction == 'short' and current_price >= ob['bottom']:
            ob['is_mitigated'] = True

    # Ziyaret edilmemiş ve fiyata en yakın OB
    active_obs = [ob for ob in order_blocks if not ob['is_mitigated']]

    if not active_obs:
        return []

    # Fiyata mesafeye göre sırala
    active_obs.sort(key=lambda ob: abs(ob['midpoint'] - current_price))

    return active_obs


def find_nearest_ob(data, direction):
    """
    Güncel fiyata en yakın aktif Order Block
    """
    obs = find_order_blocks(data, direction)
    return obs[0] if obs else None


def detect_breaker_block(data, direction, lookback=50):
    """
    Breaker Block tespiti
    Order Block'un kırılmasından sonra destek/direnç değişimi

    Bullish Breaker: Bearish OB kırılınca → Destek'e döner
    Bearish Breaker: Bullish OB kırılınca → Dirençe döner
    """
    if len(data) < 10:
        return None

    current_price = float(data['close'].iloc[-1])

    if direction == 'short':
        # Bullish OB'yi bul (kırılmış olması gerekiyor)
        obs = find_order_blocks(data, 'long', lookback)
        for ob in obs:
            # Eğer fiyat bu OB'nin altında kapandıysa → Breaker Block
            if current_price < ob['bottom']:
                return {
                    'type': 'BEARISH_BREAKER',
                    'original_ob': ob,
                    'level': ob['midpoint'],   # Artık direnç
                    'top': ob['high'],
                    'bottom': ob['low'],
                    'time': ob['time']
                }

    elif direction == 'long':
        # Bearish OB'yi bul (kırılmış olması gerekiyor)
        obs = find_order_blocks(data, 'short', lookback)
        for ob in obs:
            # Eğer fiyat bu OB'nin üstünde kapandıysa → Breaker Block
            if current_price > ob['top']:
                return {
                    'type': 'BULLISH_BREAKER',
                    'original_ob': ob,
                    'level': ob['midpoint'],   # Artık destek
                    'top': ob['high'],
                    'bottom': ob['low'],
                    'time': ob['time']
                }

    return None


def is_price_in_ob(price, ob, tolerance=0.005):
    """
    Fiyat order block içinde mi?
    tolerance: %0.5 tolerans
    """
    if ob is None:
        return False

    bottom = ob['bottom'] * (1 - tolerance)
    top = ob['top'] * (1 + tolerance)

    return bottom <= price <= top
