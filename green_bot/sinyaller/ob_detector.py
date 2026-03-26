import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class OrderBlock:
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

class OBDetector:
    """Order Block Dedektörü"""
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[OrderBlock]:
        ob_list = []
        
        for i in range(2, len(df)-2):
            onceki = df.iloc[i-1]
            simdiki = df.iloc[i]
            sonraki = df.iloc[i+1]
            
            # Bullish OB (alıcılı mum)
            if (simdiki['close'] > simdiki['open'] and  # Yeşil mum
                sonraki['close'] > sonraki['open'] and  # Sonraki yeşil
                sonraki['low'] > simdiki['high']):      # Üzerinde açılış
                
                ob = OrderBlock(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    tip='BULLISH',
                    ust_seviye=simdiki['high'],
                    alt_seviye=simdiki['low'],
                    index=i,
                    tarih=df.index[i]
                )
                ob_list.append(ob)
            
            # Bearish OB (satıcılı mum)
            if (simdiki['close'] < simdiki['open'] and  # Kırmızı mum
                sonraki['close'] < sonraki['open'] and  # Sonraki kırmızı
                sonraki['high'] < simdiki['low']):      # Altında açılış
                
                ob = OrderBlock(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    tip='BEARISH',
                    ust_seviye=simdiki['high'],
                    alt_seviye=simdiki['low'],
                    index=i,
                    tarih=df.index[i]
                )
                ob_list.append(ob)
        
        logger.info(f"📦 OB bulundu: {len(ob_list)} adet")
        return ob_list

ob_detector = OBDetector()