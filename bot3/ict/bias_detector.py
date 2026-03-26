"""
green_bot/ict/bias_detector.py
Asakura (Berkay Kemal Elcim) egitim kurallariyla komple yeniden yazildi.

TEMEL KURAL: Bias = Trend + Premium/Discount ZORUNLU eslesmesi
  BEARISH + PREMIUM  -> SHORT bias  (A++ icin zorunlu)
  BULLISH + DISCOUNT -> LONG  bias  (A++ icin zorunlu)
  Digerleri          -> NEUTRAL (islem yapma!)
"""

import pandas as pd
import numpy as np
from types import SimpleNamespace
import logging

logger = logging.getLogger(__name__)


class BiasDetector:

    def get_swing_points(self, df: pd.DataFrame, lookback: int = 5):
        df = df.copy()
        df['swing_high'] = np.nan
        df['swing_low']  = np.nan
        for i in range(lookback, len(df) - lookback):
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                df.iloc[i, df.columns.get_loc('swing_high')] = df['high'].iloc[i]
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                df.iloc[i, df.columns.get_loc('swing_low')] = df['low'].iloc[i]
        return df

    def structure_bias(self, df: pd.DataFrame) -> str:
        """HH/HL veya LL/LH yapisina gore trend."""
        if df is None or len(df) < 30:
            return 'NEUTRAL'
        df2 = self.get_swing_points(df, lookback=5)
        sh = df2['swing_high'].dropna()
        sl = df2['swing_low'].dropna()
        if len(sh) < 2 or len(sl) < 2:
            return 'NEUTRAL'
        if sh.iloc[-1] > sh.iloc[-2] and sl.iloc[-1] > sl.iloc[-2]:
            return 'BULLISH'
        if sl.iloc[-1] < sl.iloc[-2] and sh.iloc[-1] < sh.iloc[-2]:
            return 'BEARISH'
        return 'NEUTRAL'

    def premium_discount_zone(self, df: pd.DataFrame, lookback: int = 50) -> dict:
        """
        Fibonacci 0.5 kurali - egitimin temel kurali.
        SHORT icin PREMIUM (0.5 ustu) zorunlu.
        LONG  icin DISCOUNT (0.5 alti) zorunlu.
        Ayrica OTE bantlari (62/70.5/79) hesaplanir.
        """
        if df is None or len(df) < lookback:
            return {'zone': 'NEUTRAL', 'strength': 0.0, 'fib_50': None}
        son  = df.tail(lookback)
        high = son['high'].max()
        low  = son['low'].min()
        if pd.isna(high) or pd.isna(low) or high <= low:
            return {'zone': 'NEUTRAL', 'strength': 0.0, 'fib_50': None}
        rng     = high - low
        fib_50  = low + rng * 0.5
        price   = df['close'].iloc[-1]
        if price > fib_50:
            zone     = 'PREMIUM'
            strength = (price - fib_50) / (high - fib_50) if (high - fib_50) > 0 else 0
        else:
            zone     = 'DISCOUNT'
            strength = (fib_50 - price) / (fib_50 - low) if (fib_50 - low) > 0 else 0
        return {
            'zone':       zone,
            'strength':   round(min(float(strength), 1.0), 3),
            'fib_50':     fib_50,
            'fib_62':     high - rng * 0.618,
            'fib_705':    high - rng * 0.705,
            'fib_79':     high - rng * 0.790,
            'fib_886':    high - rng * 0.886,
            'swing_high': high,
            'swing_low':  low,
        }

    def combined_bias(self, df: pd.DataFrame) -> str:
        structure = self.structure_bias(df)
        pd_info   = self.premium_discount_zone(df)
        zone      = pd_info['zone']
        # Egitim kurali: tam uyum = STRONG
        if structure == 'BEARISH' and zone == 'PREMIUM':
            return 'STRONG_BEARISH'
        if structure == 'BULLISH' and zone == 'DISCOUNT':
            return 'STRONG_BULLISH'
        if structure == 'BULLISH':
            return 'BULLISH'
        if structure == 'BEARISH':
            return 'BEARISH'
        return 'NEUTRAL'

    def analiz_et(self, df: pd.DataFrame) -> SimpleNamespace:
        """Ana analiz fonksiyonu."""
        bias    = self.combined_bias(df)
        pd_info = self.premium_discount_zone(df)
        yon_map = {
            'STRONG_BULLISH': 'BULLISH', 'STRONG_BEARISH': 'BEARISH',
            'BULLISH': 'BULLISH',        'BEARISH': 'BEARISH',
            'NEUTRAL': 'NEUTRAL',
        }
        return SimpleNamespace(
            yon           = yon_map.get(bias, 'NEUTRAL'),
            bias          = bias,
            structure     = self.structure_bias(df),
            pd_zone       = pd_info['zone'],
            pd_strength   = pd_info['strength'],
            fib_50        = pd_info['fib_50'],
            fib_62        = pd_info.get('fib_62'),
            fib_705       = pd_info.get('fib_705'),
            fib_79        = pd_info.get('fib_79'),
            swing_high    = pd_info.get('swing_high'),
            swing_low     = pd_info.get('swing_low'),
            # A++ icin zorunlu: SHORT=PREMIUM, LONG=DISCOUNT
            a_plus_uyumlu = bias in ('STRONG_BEARISH', 'STRONG_BULLISH'),
        )

bias_detector = BiasDetector()
