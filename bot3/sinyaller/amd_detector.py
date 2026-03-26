import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class AMDZone:
    def __init__(self, sembol: str, zaman_dilimi: str, tip: str,
                 accumulation_alt: float, accumulation_ust: float,
                 manipulation_index: int, distribution_hedef: float):
        self.sembol = sembol
        self.zaman_dilimi = zaman_dilimi
        self.tip = tip  # 'BUY' veya 'SELL'
        self.accumulation_alt = accumulation_alt
        self.accumulation_ust = accumulation_ust
        self.manipulation_index = manipulation_index
        self.distribution_hedef = distribution_hedef
        self.tespit_zamani = datetime.now()

class AMDDetector:
    """Accumulation, Manipulation, Distribution Dedektörü"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[AMDZone]:
        amd_list = []
        
        # Accumulation bölgesi ara (yatay hareket)
        for i in range(20, len(df)-10):
            son_20 = df.iloc[i-20:i]
            range_genisligi = (son_20['high'].max() - son_20['low'].min()) / son_20['low'].min()
            
            if range_genisligi < 0.02:  # %2'den az hareket (yatay)
                alt = son_20['low'].min()
                ust = son_20['high'].max()
                
                # Manipülasyon ara (sert kaçış)
                if df['close'].iloc[i] < alt or df['close'].iloc[i] > ust:
                    hedef = ust if df['close'].iloc[i] < alt else alt
                    
                    amd = AMDZone(
                        sembol=sembol,
                        zaman_dilimi=tf,
                        tip='SELL' if df['close'].iloc[i] < alt else 'BUY',
                        accumulation_alt=alt,
                        accumulation_ust=ust,
                        manipulation_index=i,
                        distribution_hedef=hedef
                    )
                    amd_list.append(amd)
        
        logger.info(f"📊 AMD bulundu: {len(amd_list)} adet")
        return amd_list

amd_detector = AMDDetector()