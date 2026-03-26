import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class OTEZone:
    def __init__(self, sembol: str, zaman_dilimi: str, tip: str,
                 fibo_62: float, fibo_705: float, fibo_79: float,
                 msb_seviye: float):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.tip = tip
        self.fibo_62 = fibo_62
        self.fibo_705 = fibo_705
        self.fibo_79 = fibo_79
        self.msb_seviye = msb_seviye
        self.tespit_zamani = datetime.now()

class OTEDetector:
    """Optimal Trade Entry Dedektörü"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[OTEZone]:
        ote_list = []
        
        # Son swing dip ve tepeyi bul
        son_30 = df.iloc[-30:]
        dip = son_30['low'].min()
        tepe = son_30['high'].max()
        
        fark = tepe - dip
        
        # ICT bantları
        fibo_62 = tepe - fark * 0.62
        fibo_705 = tepe - fark * 0.705
        fibo_79 = tepe - fark * 0.79
        
        ote = OTEZone(
            sembol=sembol,
            zaman_dilimi=tf,
            tip='BUY' if df['close'].iloc[-1] < dip else 'SELL',
            fibo_62=fibo_62,
            fibo_705=fibo_705,
            fibo_79=fibo_79,
            msb_seviye=(dip + tepe) / 2
        )
        ote_list.append(ote)
        
        logger.info(f"📐 OTE bulundu: {len(ote_list)} adet")
        return ote_list

ote_detector = OTEDetector()