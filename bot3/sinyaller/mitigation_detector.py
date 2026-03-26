import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class MitigationZone:
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

class MitigationDetector:
    """Mitigation Block Dedektörü - Order Block'ın taşınması"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[MitigationZone]:
        mitigation_list = []
        
        for i in range(3, len(df)-3):
            # Mitigation (Order Block'ın doldurulması)
            if df['close'].iloc[i] > df['open'].iloc[i]:  # Yeşil mum
                onceki_high = df['high'].iloc[i-1]
                onceki_low = df['low'].iloc[i-1]
                
                # Önceki mumun içine girdi mi?
                if df['low'].iloc[i] < onceki_high and df['high'].iloc[i] > onceki_low:
                    mitigation = MitigationZone(
                        sembol=sembol,
                        zaman_dilimi=tf,
                        tip='BULLISH',
                        ust_seviye=df['high'].iloc[i],
                        alt_seviye=df['low'].iloc[i],
                        index=i,
                        tarih=df.index[i]
                    )
                    mitigation_list.append(mitigation)
        
        logger.info(f"🛡️ Mitigation bulundu: {len(mitigation_list)} adet")
        return mitigation_list

mitigation_detector = MitigationDetector()