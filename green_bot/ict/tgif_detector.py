import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class TGIFZone:
    """TGIF (Thank God It's Friday) - Cuma Likidite Temizliği"""
    def __init__(self, sembol: str, hafta_baslangic: datetime,
                 haftalik_yon: str, biriken_likidite: float):
        self.sembol = sembol
        self.hafta_baslangic = hafta_baslangic
        self.haftalik_yon = haftalik_yon
        self.biriken_likidite = biriken_likidite
        self.cuma_temizlik = False
        self.pazartesi_sarkti = False
        self.tespit_zamani = datetime.now()

class TGIFDetector:
    """
    TGIF (Thank God It's Friday) Dedektörü
    - Hafta boyu biriken likiditeler Cuma günü temizlenir
    - Temizlenmezse Pazartesi'ye sarkar
    """
    
    def _haftalik_yon_bul(self, df_gunluk: pd.DataFrame, hafta_bas: datetime) -> str:
        """Haftanın genel yönünü bul"""
        hafta_df = df_gunluk[df_gunluk.index >= hafta_bas]
        
        if len(hafta_df) < 2:
            return 'NEUTRAL'
        
        bas_fiyat = hafta_df.iloc[0]['open']
        son_fiyat = hafta_df.iloc[-1]['close']
        
        return 'UP' if son_fiyat > bas_fiyat else 'DOWN'
    
    def _biriken_likidite_bul(self, df_gunluk: pd.DataFrame, hafta_bas: datetime) -> float:
        """Hafta boyunca biriken likidite miktarı"""
        hafta_df = df_gunluk[df_gunluk.index >= hafta_bas]
        
        if len(hafta_df) < 2:
            return 0
        
        en_yuksek = hafta_df['high'].max()
        en_dusuk = hafta_df['low'].min()
        
        return en_yuksek - en_dusuk
    
    def analiz_et(self, df_gunluk: pd.DataFrame, sembol: str) -> List[TGIFZone]:
        """TGIF yapılarını tespit et"""
        tgif_list = []
        
        if len(df_gunluk) < 10:
            return tgif_list
        
        # Son 4 haftayı kontrol et
        for i in range(4):
            hafta_bas = df_gunluk.index[-7 - i*7]
            
            # Haftalık yön
            haftalik_yon = self._haftalik_yon_bul(df_gunluk, hafta_bas)
            biriken = self._biriken_likidite_bul(df_gunluk, hafta_bas)
            
            tgif = TGIFZone(
                sembol=sembol,
                hafta_baslangic=hafta_bas,
                haftalik_yon=haftalik_yon,
                biriken_likidite=biriken
            )
            
            # Cuma gününü bul
            cuma_gun = hafta_bas + timedelta(days=4)  # Pazartesi + 4 = Cuma
            cuma_df = df_gunluk[df_gunluk.index.date == cuma_gun.date()]
            
            if not cuma_df.empty:
                cuma_mum = cuma_df.iloc[0]
                hareket = abs(cuma_mum['close'] - cuma_mum['open']) / cuma_mum['open'] * 100
                
                if hareket > 2:  # %2'den fazla hareket
                    tgif.cuma_temizlik = True
                    logger.info(f"🙏 TGIF: {sembol} - {hafta_bas.date()} CUMA temizlik")
                else:
                    tgif.pazartesi_sarkti = True
                    logger.info(f"⚠️ TGIF: {sembol} - {hafta_bas.date()} PAZARTESİ'ye sarktı")
            
            tgif_list.append(tgif)
        
        return tgif_list

tgif_detector = TGIFDetector()