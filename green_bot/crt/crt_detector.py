import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CRTSinyali:
    sembol: str
    zaman_dilimi: str
    yon: str  # 'BULLISH' veya 'BEARISH'
    parent_high: float
    parent_low: float
    parent_open: float
    parent_close: float
    parent_govde_ust: float
    parent_govde_alt: float
    parent_igne_ust: float
    parent_igne_alt: float
    manipulasyon_tarihi: datetime
    manipulasyon_yonu: str  # 'HIGH' veya 'LOW'
    manipulasyon_seviyesi: float
    entry: float
    stop_loss: float
    hedef: float
    risk_reward: float = 0.0
    guven_skoru: float = 0.0
    tespit_zamani: datetime = datetime.now()


class CRTDetector:
    """
    CRT (Candle Range Theory) Dedektörü - SERTLEŞTİRİLMİŞ VERSİYON
    - 1. mum (parent) kapanış yapar
    - 2. mum sadece iğneleriyle 1. mumun high/low'unu alır
    - 2. mumun gövdesi 1. mumun gövdesini KESİNLİKLE geçmez
    - Parent mumda belirgin iğne olmalı
    """
    
    def __init__(self):
        self.min_wick_ratio = 0.4      # %40 iğne (daha belirgin)
        self.max_candle_age = 10       # Son 10 mum (daha güncel)
        self.tolerans = 0.00001        # Neredeyse sıfır tolerans
        
    def _igne_orani_hesapla(self, mum: pd.Series) -> Tuple[float, float, float]:
        """
        Mumun iğne oranlarını hesapla
        Returns: (ust_igne_orani, alt_igne_orani, toplam_igne_orani)
        """
        govde = abs(mum['close'] - mum['open'])
        toplam_range = mum['high'] - mum['low']
        
        if toplam_range == 0:
            return 0, 0, 0
        
        ust_igne = mum['high'] - max(mum['close'], mum['open'])
        alt_igne = min(mum['close'], mum['open']) - mum['low']
        
        ust_igne_orani = ust_igne / toplam_range
        alt_igne_orani = alt_igne / toplam_range
        toplam_igne_orani = (ust_igne + alt_igne) / toplam_range
        
        return ust_igne_orani, alt_igne_orani, toplam_igne_orani
    
    def _govde_icice_mi(self, mum1_govde_ust: float, mum1_govde_alt: float,
                        mum2_govde_ust: float, mum2_govde_alt: float) -> bool:
        """
        2. mumun gövdesi 1. mumun gövdesi içinde mi? (SIFIR TOLERANS)
        """
        return (mum2_govde_ust <= mum1_govde_ust and 
                mum2_govde_alt >= mum1_govde_alt)
    
    def _sweep_kontrol(self, mum1: pd.Series, mum2: pd.Series) -> Tuple[bool, bool, float, str]:
        """
        Sweep kontrolü - SADECE iğne ile sweep aranır
        """
        high_sweep = False
        low_sweep = False
        sweep_seviye = 0
        sweep_yonu = ""
        
        # Mum1'in iğne oranları
        ust_igne_orani, alt_igne_orani, _ = self._igne_orani_hesapla(mum1)
        
        # HIGH sweep - SADECE iğne ile olmalı
        if (mum2['high'] > mum1['high'] and 
            ust_igne_orani >= self.min_wick_ratio and  # Parent'ta iğne VAR
            mum2['close'] < mum1['high']):             # Kapanış parent high altında
            
            high_sweep = True
            sweep_seviye = mum2['high']
            sweep_yonu = "HIGH"
        
        # LOW sweep - SADECE iğne ile olmalı
        if (mum2['low'] < mum1['low'] and 
            alt_igne_orani >= self.min_wick_ratio and  # Parent'ta iğne VAR
            mum2['close'] > mum1['low']):              # Kapanış parent low üstünde
            
            low_sweep = True
            sweep_seviye = mum2['low']
            sweep_yonu = "LOW"
        
        return high_sweep, low_sweep, sweep_seviye, sweep_yonu
    
    def _guven_skoru_hesapla(self, 
                            mum1: pd.Series, 
                            mum2: pd.Series,
                            ust_igne_orani: float,
                            alt_igne_orani: float,
                            sweep_yonu: str) -> float:
        """
        CRT sinyali için güven skoru hesapla (0-100)
        """
        skor = 70  # Başlangıç (daha yüksek)
        
        # 1. İğne oranı bonusu
        if sweep_yonu == "HIGH" and ust_igne_orani >= 0.5:
            skor += 15
        elif sweep_yonu == "LOW" and alt_igne_orani >= 0.5:
            skor += 15
        
        # 2. Sweep derinliği bonusu
        if sweep_yonu == "HIGH":
            sweep_derinlik = (mum2['high'] - mum1['high']) / mum1['high'] * 100
        else:
            sweep_derinlik = (mum1['low'] - mum2['low']) / mum1['low'] * 100
        
        if sweep_derinlik > 0.2:  # %0.2'den derin sweep
            skor += 10
        
        # 3. Kapanış bonusu
        if sweep_yonu == "HIGH" and mum2['close'] < mum1['high']:
            skor += 5
        elif sweep_yonu == "LOW" and mum2['close'] > mum1['low']:
            skor += 5
        
        return min(skor, 100)
    
    def _risk_reward_hesapla(self, entry: float, stop: float, hedef: float, yon: str) -> float:
        """
        Risk/Reward oranı hesapla
        """
        if yon == "BULLISH":
            risk = abs(entry - stop)
            reward = abs(hedef - entry)
        else:
            risk = abs(stop - entry)
            reward = abs(entry - hedef)
        
        if risk == 0:
            return 0
        
        return reward / risk
    
    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[CRTSinyali]:
        """
        CRT analizi yap - SERT KURALLAR
        """
        if len(df) < 2:
            return []
        
        sinyaller = []
        
        # Son 10 mumda CRT ara
        baslangic = max(len(df) - self.max_candle_age, 1)
        
        for i in range(baslangic, len(df)):
            
            mum1 = df.iloc[i-1]  # Parent mum (1. mum)
            mum2 = df.iloc[i]    # Manipülasyon mumu (2. mum)
            
            # 1. mumun gövde sınırları
            mum1_govde_ust = max(mum1['open'], mum1['close'])
            mum1_govde_alt = min(mum1['open'], mum1['close'])
            
            # 2. mumun gövde sınırları
            mum2_govde_ust = max(mum2['open'], mum2['close'])
            mum2_govde_alt = min(mum2['open'], mum2['close'])
            
            # İğne oranlarını hesapla
            ust_igne_orani, alt_igne_orani, _ = self._igne_orani_hesapla(mum1)
            
            # Gövde iç içe mi? (SIFIR TOLERANS)
            govde_icice = self._govde_icice_mi(
                mum1_govde_ust, mum1_govde_alt,
                mum2_govde_ust, mum2_govde_alt
            )
            
            if not govde_icice:
                continue
            
            # Sweep kontrolü (SADECE iğne ile)
            high_sweep, low_sweep, sweep_seviye, sweep_yonu = self._sweep_kontrol(mum1, mum2)
            
            if not (high_sweep or low_sweep):
                continue
            
            # =========================================
            # HIGH MANİPÜLASYONU (Bearish CRT)
            # =========================================
            if high_sweep:
                
                # Hedef = 1. mumun low'u
                hedef = mum1['low']
                
                # Entry = 2. mumun kapanışı
                entry = mum2['close']
                
                # Stop = sweep seviyesinin biraz üstü
                stop = mum1['high'] * 1.003
                
                # Risk/Reward
                rr = self._risk_reward_hesapla(entry, stop, hedef, "BEARISH")
                
                # Sadece RR iyi olanları al
                if rr < 1.5:
                    continue
                
                # Güven skoru
                guven = self._guven_skoru_hesapla(mum1, mum2, ust_igne_orani, alt_igne_orani, "HIGH")
                
                # Sadece güven skoru yüksek olanları al
                if guven < 80:
                    continue
                
                sinyal = CRTSinyali(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    yon='BEARISH',
                    parent_high=mum1['high'],
                    parent_low=mum1['low'],
                    parent_open=mum1['open'],
                    parent_close=mum1['close'],
                    parent_govde_ust=mum1_govde_ust,
                    parent_govde_alt=mum1_govde_alt,
                    parent_igne_ust=mum1['high'] - mum1_govde_ust,
                    parent_igne_alt=mum1_govde_alt - mum1['low'],
                    manipulasyon_tarihi=df.index[i],
                    manipulasyon_yonu='HIGH',
                    manipulasyon_seviyesi=mum2['high'],
                    entry=entry,
                    stop_loss=stop,
                    hedef=hedef,
                    risk_reward=rr,
                    guven_skoru=guven
                )
                sinyaller.append(sinyal)
                
                logger.info(f"📊 CRT BEARISH: {sembol} - Hedef: {hedef:.4f} - RR: {rr:.2f} - Güven: %{guven:.0f}")
                continue
            
            # =========================================
            # LOW MANİPÜLASYONU (Bullish CRT)
            # =========================================
            if low_sweep:
                
                # Hedef = 1. mumun high'ı
                hedef = mum1['high']
                
                # Entry = 2. mumun kapanışı
                entry = mum2['close']
                
                # Stop = sweep seviyesinin biraz altı
                stop = mum1['low'] * 0.997
                
                # Risk/Reward
                rr = self._risk_reward_hesapla(entry, stop, hedef, "BULLISH")
                
                if rr < 1.5:
                    continue
                
                # Güven skoru
                guven = self._guven_skoru_hesapla(mum1, mum2, ust_igne_orani, alt_igne_orani, "LOW")
                
                if guven < 80:
                    continue
                
                sinyal = CRTSinyali(
                    sembol=sembol,
                    zaman_dilimi=tf,
                    yon='BULLISH',
                    parent_high=mum1['high'],
                    parent_low=mum1['low'],
                    parent_open=mum1['open'],
                    parent_close=mum1['close'],
                    parent_govde_ust=mum1_govde_ust,
                    parent_govde_alt=mum1_govde_alt,
                    parent_igne_ust=mum1['high'] - mum1_govde_ust,
                    parent_igne_alt=mum1_govde_alt - mum1['low'],
                    manipulasyon_tarihi=df.index[i],
                    manipulasyon_yonu='LOW',
                    manipulasyon_seviyesi=mum2['low'],
                    entry=entry,
                    stop_loss=stop,
                    hedef=hedef,
                    risk_reward=rr,
                    guven_skoru=guven
                )
                sinyaller.append(sinyal)
                
                logger.info(f"📊 CRT BULLISH: {sembol} - Hedef: {hedef:.4f} - RR: {rr:.2f} - Güven: %{guven:.0f}")
        
        return sinyaller


crt_detector = CRTDetector()
