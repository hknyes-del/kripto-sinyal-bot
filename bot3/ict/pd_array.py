import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class PDArray:
    """Price Delivery Array"""
    def __init__(self, sembol: str, tip: str, hedef: float, yon: str):
        self.sembol = sembol
        self.tip = tip  # 'BUY' veya 'SELL'
        self.hedef = hedef
        self.yon = yon
        self.manipulasyon = None
        self.order_block = None
        self.fvg = None
        self.tespit_zamani = datetime.now()

class PDArrayDetector:
    """
    Price Delivery Array Dedektörü
    - Manipülasyon + Displacement + OB + FVG + Range hedefi
    """
    
    def analiz_et(self, df: pd.DataFrame, sembol: str) -> List[PDArray]:
        """PD Array tespit et"""
        pd_list = []
        
        if len(df) < 20:
            return pd_list
        
        # Son 20 mumda manipülasyon ara
        son_20 = df.iloc[-20:]
        
        # Dip manipülasyonu (düşüp çıkma)
        dip = son_20['low'].min()
        dip_index = son_20['low'].idxmin()
        
        if dip_index < son_20.index[-1]:  # Dip son mum değilse
            dip_sonrasi = son_20.loc[dip_index:]
            
            # %2'den fazla yükselmiş mi?
            if (dip_sonrasi['high'].max() - dip) / dip > 0.02:
                hedef = dip_sonrasi['high'].max() * 1.01
                
                pd_array = PDArray(
                    sembol=sembol,
                    tip='BUY',
                    hedef=hedef,
                    yon='UP'
                )
                pd_list.append(pd_array)
                logger.info(f"📦 PD Array (BUY): {sembol} - Hedef: {hedef:.4f}")
        
        # Tepe manipülasyonu (çıkıp düşme)
        tepe = son_20['high'].max()
        tepe_index = son_20['high'].idxmax()
        
        if tepe_index < son_20.index[-1]:  # Tepe son mum değilse
            tepe_sonrasi = son_20.loc[tepe_index:]
            
            if (tepe - tepe_sonrasi['low'].min()) / tepe > 0.02:
                hedef = tepe_sonrasi['low'].min() * 0.99
                
                pd_array = PDArray(
                    sembol=sembol,
                    tip='SELL',
                    hedef=hedef,
                    yon='DOWN'
                )
                pd_list.append(pd_array)
                logger.info(f"📦 PD Array (SELL): {sembol} - Hedef: {hedef:.4f}")
        
        return pd_list

pd_array_detector = PDArrayDetector()