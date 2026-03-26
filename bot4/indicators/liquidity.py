"""
Likidite Havuzları Tespiti
Equal Highs/Lows (Görece Eşit Tepe/Dip)
Stop hunt bölgeleri
"""

import pandas as pd
import numpy as np


def find_equal_highs_lows(data, tolerance_pct=0.003, lookback=50):
    """
    Görece eşit tepe ve dip noktaları bul
    Bunlar likidite taşıyan kritik bölgelerdir

    tolerance_pct: Kaç yüzde fark olursa "eşit" sayılır (%0.3 default)
    """
    if len(data) < 10:
        return [], []

    subset = data.tail(lookback).copy()
    highs = subset['high'].values
    lows = subset['low'].values

    eq_highs = []
    eq_lows = []

    # Equal Highs: Birbirine yakın tepe noktaları
    for i in range(len(subset) - 1):
        for j in range(i + 1, len(subset)):
            diff_pct = abs(highs[i] - highs[j]) / highs[i]
            if diff_pct <= tolerance_pct:
                level = (highs[i] + highs[j]) / 2
                eq_highs.append({
                    'level': float(level),
                    'idx_a': i,
                    'idx_b': j,
                    'time_a': subset.index[i],
                    'time_b': subset.index[j],
                    'high_a': float(highs[i]),
                    'high_b': float(highs[j]),
                    'type': 'EQUAL_HIGH'
                })
                break  # Gruplama için sadece ilk eşleşme

    # Equal Lows: Birbirine yakın dip noktaları
    for i in range(len(subset) - 1):
        for j in range(i + 1, len(subset)):
            diff_pct = abs(lows[i] - lows[j]) / lows[i]
            if diff_pct <= tolerance_pct:
                level = (lows[i] + lows[j]) / 2
                eq_lows.append({
                    'level': float(level),
                    'idx_a': i,
                    'idx_b': j,
                    'time_a': subset.index[i],
                    'time_b': subset.index[j],
                    'low_a': float(lows[i]),
                    'low_b': float(lows[j]),
                    'type': 'EQUAL_LOW'
                })
                break

    return eq_highs, eq_lows


def find_liquidity_pools(data, direction, lookback=50):
    """
    Yönü verilen trade için hedef likidite havuzunu bul

    Long için → Equal Highs (fiyatın gitmek isteyeceği yer)
    Short için → Equal Lows (fiyatın gitmek isteyeceği yer)
    """
    eq_highs, eq_lows = find_equal_highs_lows(data, lookback=lookback)
    current_price = float(data['close'].iloc[-1])

    if direction == 'long':
        # Fiyatın üzerindeki eşit tepeler hedef
        targets = [h for h in eq_highs if h['level'] > current_price]
        targets.sort(key=lambda x: x['level'])  # En yakın önce
        return targets[:3]  # İlk 3 hedef

    elif direction == 'short':
        # Fiyatın altındaki eşit dipler hedef
        targets = [l for l in eq_lows if l['level'] < current_price]
        targets.sort(key=lambda x: x['level'], reverse=True)  # En yakın önce
        return targets[:3]

    return []


def detect_stop_hunt(data, lookback=10):
    """
    Stop-hunt hareketi tespiti
    Hızlı iğne bırakıp geri dönen mumları tespit et (Judas Swing mantığı)
    """
    if len(data) < lookback:
        return None

    subset = data.tail(lookback).copy()
    last = subset.iloc[-1]

    body_size = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['close'], last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']

    # Uzun iğne: Gövdenin en az 2 katı
    has_long_upper_wick = upper_wick > body_size * 2
    has_long_lower_wick = lower_wick > body_size * 2

    if has_long_upper_wick and last['close'] < last['open']:
        return {
            'type': 'BEARISH_STOP_HUNT',
            'wick_high': float(last['high']),
            'body_close': float(last['close']),
            'wick_ratio': round(upper_wick / body_size, 2) if body_size > 0 else 0,
            'time': subset.index[-1]
        }

    if has_long_lower_wick and last['close'] > last['open']:
        return {
            'type': 'BULLISH_STOP_HUNT',
            'wick_low': float(last['low']),
            'body_close': float(last['close']),
            'wick_ratio': round(lower_wick / body_size, 2) if body_size > 0 else 0,
            'time': subset.index[-1]
        }

    return None
