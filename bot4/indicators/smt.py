"""
SMT (Smart Money Technique) Divergence Tespiti
Korele paritelerin uyumsuzluğunu tespit eder
Örnek: BTC tepe alırken ETH almıyor → Bearish SMT
"""

import pandas as pd
import numpy as np


def detect_smt_divergence(data_a, data_b, lookback=20):
    """
    İki korele paritenin SMT uyumsuzluğunu tespit et

    Parametreler:
        data_a: Ana paritenin OHLCV verisi (örn: BTC)
        data_b: Korele paritenin OHLCV verisi (örn: ETH)
        lookback: Kaç mum geriye bakılacak

    Döndürür: SMT sinyali dict veya None
    """
    if data_a is None or data_b is None:
        return None

    if len(data_a) < lookback or len(data_b) < lookback:
        return None

    # Son N muma bak
    a = data_a.tail(lookback).copy()
    b = data_b.tail(lookback).copy()

    # Swing high ve low bul (her iki parite için)
    highs_a, lows_a = _find_simple_swings(a)
    highs_b, lows_b = _find_simple_swings(b)

    if len(highs_a) < 2 or len(highs_b) < 2:
        return None
    if len(lows_a) < 2 or len(lows_b) < 2:
        return None

    result = None

    # ---- Bearish SMT ----
    # A yeni tepe yaparken B yapamıyor → Bearish Divergence
    last_high_a = highs_a[-1]['price']
    prev_high_a = highs_a[-2]['price']
    last_high_b = highs_b[-1]['price']
    prev_high_b = highs_b[-2]['price']

    if last_high_a > prev_high_a and last_high_b <= prev_high_b:
        result = {
            'type': 'BEARISH_SMT',
            'direction': 'short',
            'symbol_a_high': float(last_high_a),
            'symbol_b_high': float(last_high_b),
            'description': 'A yeni tepe yaparken B yapamıyor',
            'strength': _smt_strength(last_high_a, prev_high_a, last_high_b, prev_high_b),
            'time': highs_a[-1]['time']
        }

    # ---- Bullish SMT ----
    # A yeni dip yaparken B yapamıyor → Bullish Divergence
    last_low_a = lows_a[-1]['price']
    prev_low_a = lows_a[-2]['price']
    last_low_b = lows_b[-1]['price']
    prev_low_b = lows_b[-2]['price']

    if last_low_a < prev_low_a and last_low_b >= prev_low_b:
        result = {
            'type': 'BULLISH_SMT',
            'direction': 'long',
            'symbol_a_low': float(last_low_a),
            'symbol_b_low': float(last_low_b),
            'description': 'A yeni dip yaparken B yapamıyor',
            'strength': _smt_strength(prev_low_a, last_low_a, prev_low_b, last_low_b),
            'time': lows_a[-1]['time']
        }

    return result


def _find_simple_swings(data, window=3):
    """
    Basit swing high ve low tespiti
    """
    highs = []
    lows = []

    h = data['high'].values
    l = data['low'].values

    for i in range(window, len(data) - window):
        # Swing high
        if h[i] == max(h[i - window:i + window + 1]):
            highs.append({'price': h[i], 'index': i, 'time': data.index[i]})

        # Swing low
        if l[i] == min(l[i - window:i + window + 1]):
            lows.append({'price': l[i], 'index': i, 'time': data.index[i]})

    return highs, lows


def _smt_strength(p1, p2, p3, p4):
    """
    SMT uyumsuzluğunun gücünü hesapla (0.0 - 1.0)
    """
    try:
        diff_a = abs(p1 - p2) / p2
        diff_b = abs(p3 - p4) / p4
        divergence = abs(diff_a - diff_b)
        return round(min(divergence * 10, 1.0), 3)
    except:
        return 0.5
