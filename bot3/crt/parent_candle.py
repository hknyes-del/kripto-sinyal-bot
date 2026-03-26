import pandas as pd
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ParentCandle:
    """Ana Mum (Parent Candle)"""
    def __init__(self, sembol: str, zaman_dilimi: str, index: int, tarih: datetime,
                 high: float, low: float, open: float, close: float):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.index = index
        self.tarih = tarih
        self.high = high
        self.low = low
        self.open = open
        self.close = close
        self.orta = (high + low) / 2

class ParentCandleDetector:
    """Parent Candle bulucu"""
    
    def son_parent_bul(self, df: pd.DataFrame, sembol: str, tf: str) -> Optional[ParentCandle]:
        """Son mumu parent olarak al"""
        if len(df) < 2:
            return None
        
        mum = df.iloc[-2]  # Bir önceki mum
        return ParentCandle(
            sembol=sembol,
            zaman_dilimi=tf,
            index=len(df)-2,
            tarih=df.index[-2],
            high=mum['high'],
            low=mum['low'],
            open=mum['open'],
            close=mum['close']
        )

parent_candle_detector = ParentCandleDetector()