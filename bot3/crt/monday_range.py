import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class MondayRange:
    def __init__(self, tarih: datetime, low: float, high: float):
        self.tarih = tarih
        self.low = low
        self.high = high
        self.orta = (low + high) / 2
        self.manipule_edildi = None
        
        range_height = high - low
        self.kirilim_1618 = high + range_height * 0.618
        self.kirilim_2272 = high + range_height * 1.272
        self.kirilim_2618 = high + range_height * 1.618

class MondayRangeDetector:
    
    def _pazartesi_mi(self, tarih: datetime) -> bool:
        return tarih.weekday() == 0
    
    def _pazartesi_range_bul(self, df: pd.DataFrame, gun: datetime) -> Optional[MondayRange]:
        gun_df = df[df.index.date == gun.date()]
        if gun_df.empty:
            return None
        
        return MondayRange(
            tarih=gun,
            low=gun_df['low'].min(),
            high=gun_df['high'].max()
        )
    
    def _manipulasyon_kontrol(self, df: pd.DataFrame, mr: MondayRange) -> bool:
        mr_sonrasi = df[df.index > mr.tarih + timedelta(days=1)]
        
        for idx, mum in mr_sonrasi.iterrows():
            if mum['high'] > mr.high:
                for j in range(1, 5):
                    if idx + j < len(df):
                        if df.iloc[idx+j]['close'] < mr.high:
                            mr.manipule_edildi = 'HIGH'
                            return True
                break
            
            if mum['low'] < mr.low:
                for j in range(1, 5):
                    if idx + j < len(df):
                        if df.iloc[idx+j]['close'] > mr.low:
                            mr.manipule_edildi = 'LOW'
                            return True
                break
        
        return False
    
    def analiz_et(self, df: pd.DataFrame, sembol: str) -> List[MondayRange]:
        sonuclar = []
        son_tarih = df.index[-1]
        
        for i in range(5):
            gun = son_tarih - timedelta(days=i*7)
            while gun.weekday() != 0:
                gun -= timedelta(days=1)
            
            mr = self._pazartesi_range_bul(df, gun)
            if mr and self._manipulasyon_kontrol(df, mr):
                sonuclar.append(mr)
                logger.info(f"📅 Monday Range: {gun.date()} - {mr.manipule_edildi}")
        
        return sonuclar

monday_range_detector = MondayRangeDetector()