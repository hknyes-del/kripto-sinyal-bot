import pandas as pd
from datetime import datetime
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class CRTSinyali:
    """CRT Yapısı Bildirimi - Sadece tespit, işlem önerisi yok"""
    def __init__(self, sembol: str, htf: str, 
                 parent_tarih, parent_high: float, parent_low: float,
                 sweep_tarih, sweep_yon: str, sweep_seviye: float):
        self.sembol = sembol
        self.htf = htf          # '1D' veya '4H'
        self.parent_tarih = parent_tarih
        self.parent_high = parent_high
        self.parent_low = parent_low
        self.sweep_tarih = sweep_tarih
        self.sweep_yon = sweep_yon  # 'yukari' veya 'asagi'
        self.sweep_seviye = sweep_seviye
        self.tespit_zamani = datetime.now()

class CRTDetector:
    """
    CRT (Candle Range Theory) Tespit Dedektörü
    Sadece Parent Candle + Likidite Süpürme (Sweep) kontrolü yapar.
    MSB+FVG beklemez, sadece yapıyı bildirir.
    """
    
    def __init__(self):
        pass
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, htf_adi: str = '1D') -> List[CRTSinyali]:
        """
        CRT yapısını tespit eder.
        
        Args:
            df: Yüksek zaman dilimi verisi (1D veya 4H)
            sembol: Coin sembolü
            htf_adi: '1D' veya '4H'
        
        Returns:
            List[CRTSinyali]: Tespit edilen CRT yapıları
        """
        sinyaller = []
        
        if len(df) < 2:
            logger.warning(f"{sembol} {htf_adi}: Yetersiz veri")
            return sinyaller
        
        try:
            # Parent Candle (bir önceki mum)
            parent = df.iloc[-2]
            # Current Candle (son mum)
            current = df.iloc[-1]
            
            # 1. Üst tarafta likidite süpürme kontrolü
            # - Fiyat parent high'ı geçti
            # - Mum parent high üstünde iğne bıraktı
            # - Kapanış parent high altında
            yukari_sweep = (
                current['high'] > parent['high'] and 
                current['close'] < parent['high']
            )
            
            # 2. Alt tarafta likidite süpürme kontrolü
            # - Fiyat parent low'u geçti
            # - Mum parent low altında iğne bıraktı
            # - Kapanış parent low üstünde
            asagi_sweep = (
                current['low'] < parent['low'] and 
                current['close'] > parent['low']
            )
            
            if yukari_sweep:
                sinyal = CRTSinyali(
                    sembol=sembol,
                    htf=htf_adi,
                    parent_tarih=parent.name,
                    parent_high=parent['high'],
                    parent_low=parent['low'],
                    sweep_tarih=current.name,
                    sweep_yon='yukari',
                    sweep_seviye=current['high']
                )
                sinyaller.append(sinyal)
                logger.info(f"📢 {sembol} {htf_adi} - ÜST likidite süpürüldü @ {current['high']:.4f}")
            
            if asagi_sweep:
                sinyal = CRTSinyali(
                    sembol=sembol,
                    htf=htf_adi,
                    parent_tarih=parent.name,
                    parent_high=parent['high'],
                    parent_low=parent['low'],
                    sweep_tarih=current.name,
                    sweep_yon='asagi',
                    sweep_seviye=current['low']
                )
                sinyaller.append(sinyal)
                logger.info(f"📢 {sembol} {htf_adi} - ALT likidite süpürüldü @ {current['low']:.4f}")
            
        except Exception as e:
            logger.error(f"CRT analiz hatası {sembol} {htf_adi}: {e}")
        
        return sinyaller

# Global CRT dedektörü
crt_detector = CRTDetector()