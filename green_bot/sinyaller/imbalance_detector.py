import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class ImbalanceZone:
    def __init__(self, sembol: str, zaman_dilimi: str, tip: str,
                 ust_seviye: float, alt_seviye: float,
                 baslangic_index: int, bitis_index: int):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.tip = tip  # 'BSI' veya 'SSI'
        self.ust_seviye = ust_seviye
        self.alt_seviye = alt_seviye
        self.baslangic_index = baslangic_index
        self.bitis_index = bitis_index
        self.orta_nokta = (ust_seviye + alt_seviye) / 2
        self.tespit_zamani = datetime.now()

class ImbalanceDetector:
    """Imbalance (BSI/SSI) Dedektörü"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[ImbalanceZone]:
        imbalance_list = []
        
        for i in range(2, len(df)-1):
            onceki = df.iloc[i-2]
            simdiki = df.iloc[i-1]
            sonraki = df.iloc[i]
            
            # BSI (Buy Side Imbalance) - yükseliş
            if (onceki['close'] > onceki['open'] and
                simdiki['close'] > simdiki['open'] and
                sonraki['close'] > sonraki['open']):
                
                if simdiki['low'] > onceki['high']:
                    imbalance = ImbalanceZone(
                        sembol=sembol,
                        zaman_dilimi=tf,
                        tip='BSI',
                        ust_seviye=simdiki['low'],
                        alt_seviye=onceki['high'],
                        baslangic_index=i-2,
                        bitis_index=i
                    )
                    imbalance_list.append(imbalance)
            
            # SSI (Sell Side Imbalance) - düşüş
            if (onceki['close'] < onceki['open'] and
                simdiki['close'] < simdiki['open'] and
                sonraki['close'] < sonraki['open']):
                
                if simdiki['high'] < onceki['low']:
                    imbalance = ImbalanceZone(
                        sembol=sembol,
                        zaman_dilimi=tf,
                        tip='SSI',
                        ust_seviye=onceki['low'],
                        alt_seviye=simdiki['high'],
                        baslangic_index=i-2,
                        bitis_index=i
                    )
                    imbalance_list.append(imbalance)
        
        logger.info(f"⚖️ Imbalance bulundu: {len(imbalance_list)} adet")
        return imbalance_list

imbalance_detector = ImbalanceDetector()