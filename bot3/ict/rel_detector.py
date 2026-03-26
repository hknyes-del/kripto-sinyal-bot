import pandas as pd
from datetime import datetime
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class RELZone:
    def __init__(self, sembol: str, tip: str, seviye1: float, seviye2: float,
                 tarih1: datetime, tarih2: datetime):
        self.sembol = sembol
        self.tip = tip
        self.seviye1 = seviye1
        self.seviye2 = seviye2
        self.tarih1 = tarih1
        self.tarih2 = tarih2
        self.ortalama = (seviye1 + seviye2) / 2
        self.tespit_zamani = datetime.now()

class RELDetector:
    
    def __init__(self, tolerans=0.001):
        self.tolerans = tolerans
    
    def _swing_bul(self, df: pd.DataFrame, tip: str) -> List[Tuple[int, float, datetime]]:
        noktalar = []
        for i in range(5, len(df)-5):
            if tip == 'HIGH':
                if df['high'].iloc[i] == max(df['high'].iloc[i-5:i+6]):
                    noktalar.append((i, df['high'].iloc[i], df.index[i]))
            else:
                if df['low'].iloc[i] == min(df['low'].iloc[i-5:i+6]):
                    noktalar.append((i, df['low'].iloc[i], df.index[i]))
        return noktalar
    
    def _ayni_bolge_mi(self, f1: float, f2: float) -> bool:
        fark = abs(f1 - f2) / min(f1, f2)
        return fark < self.tolerans
    
    def analiz_et(self, df: pd.DataFrame, sembol: str) -> List[RELZone]:
        rel_zonelar = []
        
        tepeler = self._swing_bul(df, 'HIGH')
        for i in range(len(tepeler)):
            for j in range(i+1, len(tepeler)):
                if self._ayni_bolge_mi(tepeler[i][1], tepeler[j][1]):
                    rel_zonelar.append(RELZone(
                        sembol=sembol,
                        tip='REH',
                        seviye1=tepeler[i][1],
                        seviye2=tepeler[j][1],
                        tarih1=tepeler[i][2],
                        tarih2=tepeler[j][2]
                    ))
        
        dipler = self._swing_bul(df, 'LOW')
        for i in range(len(dipler)):
            for j in range(i+1, len(dipler)):
                if self._ayni_bolge_mi(dipler[i][1], dipler[j][1]):
                    rel_zonelar.append(RELZone(
                        sembol=sembol,
                        tip='REL',
                        seviye1=dipler[i][1],
                        seviye2=dipler[j][1],
                        tarih1=dipler[i][2],
                        tarih2=dipler[j][2]
                    ))
        
        logger.info(f"📊 REL bulundu: {len(rel_zonelar)} adet")
        return rel_zonelar

rel_detector = RELDetector()
