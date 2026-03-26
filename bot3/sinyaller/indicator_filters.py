# sinyaller/indicator_filters.py
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class IndicatorFilters:
    """%85-90 Win-Rate için ek onay filtreleri"""

    def check_rsi_onay(self, df: pd.DataFrame, yon: str) -> bool:
        """RSI 30/70 ve Uyumsuzluk kontrolü"""
        try:
            if len(df) < 14: return False
            
            # Basit RSI hesaplama (veri_topla'da yoksa diye)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1+rs))
            
            current_rsi = rsi.iloc[-1]
            
            if yon == 'BULLISH':
                # Aşırı satım veya pozitif uyumsuzluk (basitleştirilmiş)
                return current_rsi < 40 # Daha esnek 40, çok katı 30
            else:
                # Aşırı alım veya negatif uyumsuzluk
                return current_rsi > 60
        except Exception as e:
            logger.error(f"RSI Onay hatası: {e}")
            return False

    def check_macd_momentum(self, df: pd.DataFrame, yon: str) -> bool:
        """MACD Histogram yön/hız onayı"""
        try:
            if 'close' not in df: return False
            
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            hist = macd - signal
            
            last_hist = hist.iloc[-1]
            prev_hist = hist.iloc[-2]
            
            if yon == 'BULLISH':
                return last_hist > prev_hist # Momentum artıyor
            else:
                return last_hist < prev_hist # Momentum düşüyor
        except Exception as e:
            logger.error(f"MACD Onay hatası: {e}")
            return False

    def check_bb_deviation(self, df: pd.DataFrame, yon: str) -> bool:
        """Bollinger Bantları sapma onayı"""
        try:
            if len(df) < 20: return False
            
            sma = df['close'].rolling(window=20).mean()
            std = df['close'].rolling(window=20).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            
            last_price = df['close'].iloc[-1]
            last_low = df['low'].iloc[-1]
            last_high = df['high'].iloc[-1]
            
            if yon == 'BULLISH':
                return last_low <= lower_band.iloc[-1] * 1.002 # Alt banda yakın veya dışarda
            else:
                return last_high >= upper_band.iloc[-1] * 0.998 # Üst banda yakın veya dışarda
        except Exception as e:
            logger.error(f"BB Onay hatası: {e}")
            return False

    def get_fib_ote_zone(self, df: pd.DataFrame, yon: str) -> tuple:
        """Son swing hareketine göre OTE (0.618 - 0.786) hesaplar"""
        try:
            if len(df) < 50: return None, None
            
            # Son 50 mumdaki en yüksek ve en düşük
            recent_df = df.iloc[-50:]
            high = recent_df['high'].max()
            low = recent_df['low'].min()
            diff = high - low
            
            if yon == 'BULLISH':
                # Alım için OTE (Yukarı trendde düzeltme)
                ote_start = high - (diff * 0.618)
                ote_end = high - (diff * 0.786)
                return ote_start, ote_end
            else:
                # Satım için OTE (Aşağı trendde düzeltme)
                ote_start = low + (diff * 0.618)
                ote_end = low + (diff * 0.786)
                return ote_start, ote_end
        except:
            return None, None

indicator_filters = IndicatorFilters()
