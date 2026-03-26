import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

from .parent_candle import parent_candle_detector, ParentCandle

logger = logging.getLogger(__name__)

class CRTSinyali:
    def __init__(self, sembol: str, zaman_dilimi: str, parent: ParentCandle,
                 manipulasyon_yonu: str, manipulasyon_tarih: datetime, hedef: float):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.parent = parent
        self.manipulasyon_yonu = manipulasyon_yonu
        self.manipulasyon_tarih = manipulasyon_tarih
        self.hedef = hedef
        self.tespit_zamani = datetime.now()

class CRTDetector:
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[CRTSinyali]:
        sinyaller = []
        
        if len(df) < 5:
            return sinyaller
        
        parent = parent_candle_detector.son_parent_bul(df, sembol, tf)
        if not parent:
            return sinyaller
        
        for i in range(parent.index+1, min(parent.index+10, len(df))):
            mum = df.iloc[i]
            
            # High manipülasyonu
            if mum['high'] > parent.high:
                for j in range(i+1, min(i+5, len(df))):
                    if df.iloc[j]['close'] < parent.high:
                        sinyal = CRTSinyali(
                            sembol=sembol,
                            zaman_dilimi=tf,
                            parent=parent,
                            manipulasyon_yonu='HIGH',
                            manipulasyon_tarih=df.index[i],
                            hedef=parent.low
                        )
                        sinyaller.append(sinyal)
                        logger.info(f"🕯️ CRT: {sembol} - HIGH manipülasyon")
                        break
            
            # Low manipülasyonu
            if mum['low'] < parent.low:
                for j in range(i+1, min(i+5, len(df))):
                    if df.iloc[j]['close'] > parent.low:
                        sinyal = CRTSinyali(
                            sembol=sembol,
                            zaman_dilimi=tf,
                            parent=parent,
                            manipulasyon_yonu='LOW',
                            manipulasyon_tarih=df.index[i],
                            hedef=parent.high
                        )
                        sinyaller.append(sinyal)
                        logger.info(f"🕯️ CRT: {sembol} - LOW manipülasyon")
                        break
        
        return sinyaller

crt_detector = CRTDetector()