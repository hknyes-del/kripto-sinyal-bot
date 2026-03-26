"""
Fair Value Gap (FVG) tespiti - Geliştirilmiş versiyon
ICT kurallarına göre: MSB sonrası oluşan güçlü FVG
Bisi (Buy Side Imbalance) ve Sibi (Sell Side Imbalance)
"""

import pandas as pd
import numpy as np


def find_fvg(data, direction, lookback=50, min_size_pct=0.001):
    """
    FVG bul - Güçlü versiyon
    Döndürür: En yakın ve aktif FVG dict veya None

    min_size_pct: Minimum boşluk büyüklüğü (fiyatın %0.1'i)
    """
    if len(data) < 5:
        return None

    fvgs = find_all_fvgs(data, direction, lookback, min_size_pct)

    if not fvgs:
        return None

    current_price = float(data['close'].iloc[-1])

    # Ziyaret edilmemiş ve fiyata en yakın FVG
    active = [f for f in fvgs if not f['is_filled']]

    if not active:
        return None

    # En yakın aktif FVG
    active.sort(key=lambda f: abs(f['midpoint'] - current_price))
    return active[0]


def find_all_fvgs(data, direction, lookback=50, min_size_pct=0.001):
    """
    Belirtilen yönde tüm FVG'leri bul
    """
    if len(data) < 3:
        return []

    fvgs = []
    current_price = float(data['close'].iloc[-1])
    n = min(len(data) - 2, lookback)
    subset = data.tail(n + 2).copy()

    close = subset['close'].values
    open_ = subset['open'].values
    high = subset['high'].values
    low = subset['low'].values

    for i in range(len(subset) - 2):
        c1 = subset.iloc[i]
        c2 = subset.iloc[i + 1]
        c3 = subset.iloc[i + 2]

        if direction == 'long':
            # Bullish FVG (Sibi): 3 yeşil mum, 1.mum tepesi < 3.mum dibi
            if (c1['close'] > c1['open'] and
                    c2['close'] > c2['open'] and
                    c3['close'] > c3['open']):

                gap_bottom = c1['high']
                gap_top = c3['low']

                if gap_top > gap_bottom:
                    gap_size = (gap_top - gap_bottom) / gap_bottom
                    if gap_size >= min_size_pct:
                        midpoint = (gap_top + gap_bottom) / 2
                        # Doldurulmuş mu?
                        is_filled = current_price <= gap_bottom

                        fvgs.append({
                            'type': 'BULLISH_FVG',
                            'top': float(gap_top),
                            'bottom': float(gap_bottom),
                            'midpoint': float(midpoint),
                            'size_pct': round(gap_size * 100, 3),
                            'index': i,
                            'time': subset.index[i + 1],
                            'is_filled': is_filled
                        })

        elif direction == 'short':
            # Bearish FVG (Bisi): 3 kırmızı mum, 1.mum dibi > 3.mum tepesi
            if (c1['close'] < c1['open'] and
                    c2['close'] < c2['open'] and
                    c3['close'] < c3['open']):

                gap_top = c1['low']
                gap_bottom = c3['high']

                if gap_top > gap_bottom:
                    gap_size = (gap_top - gap_bottom) / gap_bottom
                    if gap_size >= min_size_pct:
                        midpoint = (gap_top + gap_bottom) / 2
                        # Doldurulmuş mu?
                        is_filled = current_price >= gap_top

                        fvgs.append({
                            'type': 'BEARISH_FVG',
                            'top': float(gap_top),
                            'bottom': float(gap_bottom),
                            'midpoint': float(midpoint),
                            'size_pct': round(gap_size * 100, 3),
                            'index': i,
                            'time': subset.index[i + 1],
                            'is_filled': is_filled
                        })

    return fvgs


def find_fvg_near_msb(data_ltf, msb_price, direction, search_range_pct=0.05):
    """
    MSB bölgesine yakın FVG ara
    MSB sonrası oluşan FVG en güçlü olanıdır

    msb_price: MSB kırılım fiyatı
    search_range_pct: MSB'den ne kadar uzakta aranacak (%5 default)
    """
    if data_ltf is None or len(data_ltf) < 5:
        return None

    fvgs = find_all_fvgs(data_ltf, direction)

    if not fvgs:
        return None

    # MSB bölgesine yakın FVG'leri filtrele
    near_msb = []
    for fvg in fvgs:
        distance = abs(fvg['midpoint'] - msb_price) / msb_price
        if distance <= search_range_pct:
            fvg['distance_from_msb'] = round(distance * 100, 2)
            near_msb.append(fvg)

    if not near_msb:
        return None

    # MSB'e en yakın FVG
    near_msb.sort(key=lambda f: f['distance_from_msb'])
    return near_msb[0]


def is_price_in_fvg(price, fvg, tolerance=0.003):
    """
    Fiyat FVG içinde mi?
    """
    if fvg is None:
        return False
    bottom = fvg['bottom'] * (1 - tolerance)
    top = fvg['top'] * (1 + tolerance)
    return bottom <= price <= top
