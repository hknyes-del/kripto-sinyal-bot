import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class BreakerZone:
    def __init__(self, sembol: str, zaman_dilimi: str, tip: str,
                 ust_seviye: float, alt_seviye: float,
                 index: int, tarih: datetime):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.tip = tip  # 'BULLISH' veya 'BEARISH'
        self.ust_seviye = ust_seviye
        self.alt_seviye = alt_seviye
        self.index = index
        self.tarih = tarih
        self.tespit_zamani = datetime.now()

class BreakerDetector:
    """Breaker Block Dedektörü"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[BreakerZone]:
        breaker_list = []
        
        # MSB sonrası breaker ara (basit versiyon)
        for i in range(5, len(df)-5):
            # Yükseliş trendi sonrası düşüş
            if (df['high'].iloc[i-5:i].max() > df['high'].iloc[i-10:i-5].max() and
                df['low'].iloc[i] < df['low'].iloc[i-1]):
                
                breaker = BreakerZone(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    tip='BEARISH',
                    ust_seviye=df['high'].iloc[i-1],
                    alt_seviye=df['low'].iloc[i],
                    index=i,
                    tarih=df.index[i]
                )
                breaker_list.append(breaker)
            
            # Düşüş trendi sonrası yükseliş
            if (df['low'].iloc[i-5:i].min() < df['low'].iloc[i-10:i-5].min() and
                df['high'].iloc[i] > df['high'].iloc[i-1]):
                
                breaker = BreakerZone(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    tip='BULLISH',
                    ust_seviye=df['high'].iloc[i],
                    alt_seviye=df['low'].iloc[i-1],
                    index=i,
                    tarih=df.index[i]
                )
                breaker_list.append(breaker)
        
        logger.info(f"⚔️ Breaker bulundu: {len(breaker_list)} adet")
        return breaker_list

breaker_detector = BreakerDetector()