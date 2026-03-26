# sinyaller/liquidity_detector.py
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import logging

logger = logging.getLogger(__name__)

class SuvSinyali:
    def __init__(self, sembol, tip, seviye_tipi, seviye, sweep_fiyat, yon):
        self.sembol = sembol
        self.tip = tip  # 'SWEEP'
        self.seviye_tipi = seviye_tipi  # 'PDH', 'PDL', 'ASH', 'ASL'
        self.seviye = seviye
        self.sweep_fiyat = sweep_fiyat
        self.yon = yon  # 'BULLISH' (PDL/ASL sweep), 'BEARISH' (PDH/ASH sweep)
        self.zaman = datetime.now()

class LiquidityDetector:
    def __init__(self):
        # Asya Seansı: 00:00 - 06:00 UTC (03:00 - 09:00 TR)
        self.asia_start = time(0, 0)
        self.asia_end = time(6, 0)

    def find_pdh_pdl(self, df_1d: pd.DataFrame) -> tuple:
        """Bir önceki günün High ve Low seviyelerini bulur"""
        if len(df_1d) < 2: return None, None
        
        # Son tamamlanmış günlük mum (indeks -2, çünkü -1 mevcut mumdur)
        prev_day = df_1d.iloc[-2]
        return prev_day['high'], prev_day['low']

    def find_asia_range(self, df_15m: pd.DataFrame) -> tuple:
        """Asya seansı High ve Low seviyelerini bulur"""
        try:
            # Bugünün Asya mumlarını filtrele (UTC zamanına göre)
            now = datetime.now()
            today_asia = df_15m[
                (df_15m.index.date == now.date()) & 
                (df_15m.index.time >= self.asia_start) & 
                (df_15m.index.time <= self.asia_end)
            ]
            
            if today_asia.empty:
                # Eğer bugün henüz oluşmadıysa dünün Asya seansına bak (opsiyonel ama güvenli)
                yesterday = now - timedelta(days=1)
                today_asia = df_15m[
                    (df_15m.index.date == yesterday.date()) & 
                    (df_15m.index.time >= self.asia_start) & 
                    (df_15m.index.time <= self.asia_end)
                ]

            if not today_asia.empty:
                return today_asia['high'].max(), today_asia['low'].min()
        except Exception as e:
            logger.error(f"Asya range hesaplama hatası: {e}")
            
        return None, None

    def analiz_et(self, df_ltf: pd.DataFrame, sembol: str, pdh: float, pdl: float, ash: float, asl: float):
        """Likidite süpürme (Sweep) kontrolü yapar"""
        if df_ltf.empty: return []
        
        sinyaller = []
        last_candle = df_ltf.iloc[-1]
        prev_candle = df_ltf.iloc[-2]
        
        # 1. BEARISH SWEEP (Üst likidite süpürme)
        # PDH Sweep
        if pdh and prev_candle['high'] > pdh and last_candle['close'] < pdh:
            sinyaller.append(SuvSinyali(sembol, 'SWEEP', 'PDH', pdh, prev_candle['high'], 'BEARISH'))
        
        # ASH Sweep
        if ash and prev_candle['high'] > ash and last_candle['close'] < ash:
            sinyaller.append(SuvSinyali(sembol, 'SWEEP', 'ASH', ash, prev_candle['high'], 'BEARISH'))

        # 2. BULLISH SWEEP (Alt likidite süpürme)
        # PDL Sweep
        if pdl and prev_candle['low'] < pdl and last_candle['close'] > pdl:
            sinyaller.append(SuvSinyali(sembol, 'SWEEP', 'PDL', pdl, prev_candle['low'], 'BULLISH'))
            
        # ASL Sweep
        if asl and prev_candle['low'] < asl and last_candle['close'] > asl:
            sinyaller.append(SuvSinyali(sembol, 'SWEEP', 'ASL', asl, prev_candle['low'], 'BULLISH'))

        return sinyaller

liquidity_detector = LiquidityDetector()
