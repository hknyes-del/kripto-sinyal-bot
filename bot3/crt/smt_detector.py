import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SMTUyumsuzluk:
    def __init__(self, parite1: str, parite2: str, tip: str,
                 tarih: datetime, seviye1: float, seviye2: float):
        self.parite1 = parite1
        self.parite2 = parite2
        self.tip = tip
        self.tarih = tarih
        self.seviye1 = seviye1
        self.seviye2 = seviye2
        self.tespit_zamani = datetime.now()

class SMTDetector:
    
    def __init__(self):
        self.kuzen_ciftler = [
            ('BTCUSDT', 'ETHUSDT'),
            ('XAUUSD', 'XAGUSD'),
            ('EURUSD', 'GBPUSD')
        ]
    
    def _son_tepe_kontrol(self, df1: pd.DataFrame, df2: pd.DataFrame,
                           ad1: str, ad2: str) -> Optional[SMTUyumsuzluk]:
        son_10_1 = df1.iloc[-10:]
        son_10_2 = df2.iloc[-10:]
        
        tepe1 = son_10_1['high'].max()
        tepe2 = son_10_2['high'].max()
        tepe_index1 = son_10_1['high'].idxmax()
        
        if tepe1 > son_10_1['high'].iloc[-2] and tepe2 <= son_10_2['high'].iloc[-2]:
            return SMTUyumsuzluk(ad1, ad2, 'TEPE', tepe_index1, tepe1, tepe2)
        
        return None
    
    def _son_dip_kontrol(self, df1: pd.DataFrame, df2: pd.DataFrame,
                          ad1: str, ad2: str) -> Optional[SMTUyumsuzluk]:
        son_10_1 = df1.iloc[-10:]
        son_10_2 = df2.iloc[-10:]
        
        dip1 = son_10_1['low'].min()
        dip2 = son_10_2['low'].min()
        dip_index1 = son_10_1['low'].idxmin()
        
        if dip1 < son_10_1['low'].iloc[-2] and dip2 >= son_10_2['low'].iloc[-2]:
            return SMTUyumsuzluk(ad1, ad2, 'DIP', dip_index1, dip1, dip2)
        
        return None
    
    def analiz_et(self, df_dict: Dict[str, pd.DataFrame]) -> List[SMTUyumsuzluk]:
        uyumsuzluklar = []
        
        for p1, p2 in self.kuzen_ciftler:
            if p1 not in df_dict or p2 not in df_dict:
                continue
            
            tepe = self._son_tepe_kontrol(df_dict[p1], df_dict[p2], p1, p2)
            if tepe:
                uyumsuzluklar.append(tepe)
                logger.info(f"🔗 SMT: {p1}-{p2} TEPE uyumsuzluğu")
            
            dip = self._son_dip_kontrol(df_dict[p1], df_dict[p2], p1, p2)
            if dip:
                uyumsuzluklar.append(dip)
                logger.info(f"🔗 SMT: {p1}-{p2} DİP uyumsuzluğu")
        
        return uyumsuzluklar

smt_detector = SMTDetector()