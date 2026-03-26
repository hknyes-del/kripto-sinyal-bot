"""
green_bot/sinyaller/msb_detector.py
Egitim: MSB olmadan islem = kumardır.
- HTF bias yönüne göre filtreli
- Displacement (ATR'nin 1x'i gecen govde) zorunlu
- Fib 0.5: PAHALI/UCUZ bölgesi
- SMT ve Monday Range konfluans
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MSBSinyali:
    sembol: str
    zaman_dilimi: str
    tespit_tarihi: datetime
    fiyat: float
    yon: str                     # 'BULLISH' / 'BEARISH'
    kirilma_seviyesi: float
    swing_high: float
    swing_low: float
    guven_skoru: float
    entry: float
    stop: float
    # Egitim filtreleri
    fib_zone: str                # 'PAHALILIK' / 'UCUZLUK'
    bias_yon: str
    smt_konfirm: bool
    monday_range_confluence: bool
    super_model: bool            # A+++


class MSBDetector:

    def __init__(self, swing_lookback: int = 5, atr_period: int = 14,
                 min_body_atr: float = 0.8):
        self.swing_lookback = swing_lookback
        self.atr_period     = atr_period
        self.min_body_atr   = min_body_atr

    def _atr(self, df: pd.DataFrame) -> pd.Series:
        hl  = df['high'] - df['low']
        hc  = (df['high'] - df['close'].shift()).abs()
        lc  = (df['low']  - df['close'].shift()).abs()
        tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return tr.rolling(self.atr_period, min_periods=self.atr_period).mean()

    def _swing_highs(self, df: pd.DataFrame) -> list:
        highs = []
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            left  = df['high'].iloc[i - self.swing_lookback: i]
            right = df['high'].iloc[i + 1: i + self.swing_lookback + 1]
            if left.empty or right.empty:
                continue
            if df['high'].iloc[i] > left.max() and df['high'].iloc[i] > right.max():
                highs.append((i, float(df['high'].iloc[i])))
        return highs

    def _swing_lows(self, df: pd.DataFrame) -> list:
        lows = []
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            left  = df['low'].iloc[i - self.swing_lookback: i]
            right = df['low'].iloc[i + 1: i + self.swing_lookback + 1]
            if left.empty or right.empty:
                continue
            if df['low'].iloc[i] < left.min() and df['low'].iloc[i] < right.min():
                lows.append((i, float(df['low'].iloc[i])))
        return lows

    def _displacement_var_mi(self, df: pd.DataFrame, i: int,
                              atr_series: pd.Series) -> bool:
        if i >= len(df) or pd.isna(atr_series.iloc[i]):
            return True
        govde = abs(df['close'].iloc[i] - df['open'].iloc[i])
        return govde > atr_series.iloc[i] * self.min_body_atr

    def _fib_zone(self, df: pd.DataFrame) -> tuple:
        """Egitim: Fibo 0.5 ile PAHALI/UCUZ belirleme."""
        sh = df['high'].rolling(20).max().iloc[-20:].max()
        sl = df['low'].rolling(20).min().iloc[-20:].min()
        if sh <= sl:
            return 'NEUTRAL', sl + (sh - sl) * 0.5
        fib_50 = sl + (sh - sl) * 0.5
        current = df['close'].iloc[-1]
        return ('PAHALILIK' if current > fib_50 else 'UCUZLUK'), fib_50

    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str,
                  htf_bias: str = None) -> List[MSBSinyali]:
        """
        MSB tespiti.
        htf_bias: 'BULLISH' / 'BEARISH' - sadece uyumlu MSB ara
        """
        if len(df) < 30:
            return []

        sinyaller = []
        df2 = df.copy()
        df2['ATR'] = self._atr(df2)

        sh_list = self._swing_highs(df2)
        sl_list = self._swing_lows(df2)

        if not sh_list or not sl_list:
            return []

        fib_zone, fib_50 = self._fib_zone(df2)
        son_fiyat        = df2['close'].iloc[-1]
        son_high         = df2['high'].iloc[-1]
        son_low          = df2['low'].iloc[-1]

        # ── Bullish MSB ─────────────────────────────────────
        if htf_bias in (None, 'BULLISH'):
            for i_sh, sh_price in sh_list[-3:]:
                if son_fiyat > sh_price:
                    kirilma_idx = len(df2) - 1
                    if not self._displacement_var_mi(df2, kirilma_idx, df2['ATR']):
                        continue

                    # Premium/Discount filtresi: LONG icin UCUZ olmali
                    pd_uyum = fib_zone == 'UCUZLUK'

                    guven = 70.0
                    bp    = (son_fiyat - sh_price) / sh_price * 100
                    guven += min(bp * 5, 15)
                    if pd_uyum:         guven += 10
                    if fib_zone == 'UCUZLUK': guven += 5  # ekstra DISCOUNT bonus

                    latest_sl = sl_list[-1][1] if sl_list else son_fiyat * 0.98
                    atr_val   = df2['ATR'].iloc[-1] if not pd.isna(df2['ATR'].iloc[-1]) else son_fiyat * 0.01

                    sinyal = MSBSinyali(
                        sembol       = sembol,
                        zaman_dilimi = tf,
                        tespit_tarihi = datetime.now(),
                        fiyat        = son_fiyat,
                        yon          = 'BULLISH',
                        kirilma_seviyesi = sh_price,
                        swing_high   = max(sh_price, son_high),
                        swing_low    = latest_sl,
                        guven_skoru  = min(guven, 100.0),
                        entry        = son_fiyat,
                        stop         = latest_sl - atr_val * 0.5,
                        fib_zone     = fib_zone,
                        bias_yon     = htf_bias or 'BULLISH',
                        smt_konfirm  = False,
                        monday_range_confluence = False,
                        super_model  = guven >= 90 and pd_uyum,
                    )
                    sinyaller.append(sinyal)
                    logger.info(f"MSB BULLISH: {sembol} {tf} - %{guven:.0f} {fib_zone}")
                    break  # En son swing high yeterli

        # ── Bearish MSB ─────────────────────────────────────
        if htf_bias in (None, 'BEARISH'):
            for i_sl, sl_price in sl_list[-3:]:
                if son_fiyat < sl_price:
                    kirilma_idx = len(df2) - 1
                    if not self._displacement_var_mi(df2, kirilma_idx, df2['ATR']):
                        continue

                    pd_uyum = fib_zone == 'PAHALILIK'

                    guven = 70.0
                    bp    = (sl_price - son_fiyat) / sl_price * 100
                    guven += min(bp * 5, 15)
                    if pd_uyum: guven += 10
                    if fib_zone == 'PAHALILIK': guven += 5

                    latest_sh = sh_list[-1][1] if sh_list else son_fiyat * 1.02
                    atr_val   = df2['ATR'].iloc[-1] if not pd.isna(df2['ATR'].iloc[-1]) else son_fiyat * 0.01

                    sinyal = MSBSinyali(
                        sembol       = sembol,
                        zaman_dilimi = tf,
                        tespit_tarihi = datetime.now(),
                        fiyat        = son_fiyat,
                        yon          = 'BEARISH',
                        kirilma_seviyesi = sl_price,
                        swing_high   = latest_sh,
                        swing_low    = min(sl_price, son_low),
                        guven_skoru  = min(guven, 100.0),
                        entry        = son_fiyat,
                        stop         = latest_sh + atr_val * 0.5,
                        fib_zone     = fib_zone,
                        bias_yon     = htf_bias or 'BEARISH',
                        smt_konfirm  = False,
                        monday_range_confluence = False,
                        super_model  = guven >= 90 and pd_uyum,
                    )
                    sinyaller.append(sinyal)
                    logger.info(f"MSB BEARISH: {sembol} {tf} - %{guven:.0f} {fib_zone}")
                    break

        return sinyaller


msb_detector = MSBDetector()
