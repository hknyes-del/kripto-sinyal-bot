"""
green_bot/sinyaller/fvg_detector.py
Egitim: FVG'nin 3 SARTTININ HEPSI olmali:
  1. MSB olmali (oncesinde yapi kirilimi)
  2. Likidite bosluğu: 1. ve 3. mumun igneleri ortusmuyor
  3. Hacim dengesizligi: orta mumun hacmi ortalamadan yuksek

CE noktasi = FVG midpoint (kısaltma girişleri buraya gelir)
Bolgeden displace hareket olmadan FVG GECERSIZ.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FVGSinyali:
    sembol: str
    zaman_dilimi: str
    tespit_tarihi: datetime
    fiyat: float
    yon: str
    msb_seviye: float
    msb_tarih: datetime
    fvg_bolgesi: Tuple[float, float]
    fvg_derinlik: float
    guven_skoru: float = 0.0
    entry_fiyat: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[List[float]] = None
    # Egitim alanlari
    fib_zone: str = "NEUTRAL"
    bias_yon: str = "NEUTRAL"
    crt_confluence: bool = False
    super_model: bool = False
    ce_noktasi: float = 0.0          # CE (midpoint) = kurumsal limit emri bolgesi
    sart_1_msb: bool = False         # MSB var mi?
    sart_2_bosluk: bool = False      # Likidite boslugu var mi?
    sart_3_hacim: bool = False       # Hacim dengesizligi var mi?
    sart_puan: int = 0               # Kac sart saglandi (max 3)
    bias_pd_uyumu: bool = False      # SHORT=PREMIUM, LONG=DISCOUNT uyumu


class FVGDetector:

    def __init__(self, min_fvg_buyukluk: float = 0.1):
        self.min_fvg_buyukluk = min_fvg_buyukluk

    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str,
                  msb_list: List) -> List[FVGSinyali]:
        if len(df) < 10 or not msb_list:
            return []

        sinyaller = []
        try:
            for msb in msb_list:
                msb_index = self._msb_index_bul(df, msb)
                if msb_index is None:
                    continue

                # Fib ve bias bilgileri
                fib_zone, _ = self._fib_zone(df)
                bias_yon    = self._bias_yon(df)

                for i in range(msb_index + 1, len(df) - 2):
                    m1 = df.iloc[i]
                    m2 = df.iloc[i + 1]
                    m3 = df.iloc[i + 2] if i + 2 < len(df) else None

                    # ── BULLISH FVG ──────────────────────────
                    if msb.yon == 'BULLISH' and m2['low'] > m1['high']:
                        alt = m1['high']
                        ust = m2['low']
                        buyukluk = (ust - alt) / alt * 100
                        if buyukluk < self.min_fvg_buyukluk:
                            continue

                        s1 = True  # MSB zaten var (msb_list'te)
                        s2 = m3 is not None and m3['low'] > alt  # Likidite boslugu (3. mum ignesi ortusmuyor)
                        s3 = self._hacim_dengesizligi(df, i + 1)

                        sinyal = self._sinyal_olustur(
                            sembol, tf, msb, 'BULLISH', alt, ust, df, i,
                            fib_zone, bias_yon, s1, s2, s3
                        )
                        sinyaller.append(sinyal)
                        break

                    # ── BEARISH FVG ──────────────────────────
                    elif msb.yon == 'BEARISH' and m2['high'] < m1['low']:
                        alt = m2['high']
                        ust = m1['low']
                        buyukluk = (ust - alt) / alt * 100
                        if buyukluk < self.min_fvg_buyukluk:
                            continue

                        s1 = True
                        s2 = m3 is not None and m3['high'] < ust
                        s3 = self._hacim_dengesizligi(df, i + 1)

                        sinyal = self._sinyal_olustur(
                            sembol, tf, msb, 'BEARISH', alt, ust, df, i,
                            fib_zone, bias_yon, s1, s2, s3
                        )
                        sinyaller.append(sinyal)
                        break

        except Exception as e:
            logger.error(f"FVG analiz hatasi {sembol} {tf}: {e}")
        return sinyaller

    def _hacim_dengesizligi(self, df: pd.DataFrame, idx: int) -> bool:
        """Orta mumun hacmi son 10 mumun ortalamasinin %20 ustunde mi?"""
        if idx < 5:
            return False
        ort_hacim = df['volume'].iloc[idx - 10: idx].mean()
        return df['volume'].iloc[idx] > ort_hacim * 1.2

    def _msb_index_bul(self, df: pd.DataFrame, msb) -> Optional[int]:
        for i in range(len(df) - 1, -1, -1):
            if hasattr(msb, 'tespit_tarihi') and \
               abs((df.index[i] - msb.tespit_tarihi).total_seconds()) < 3600:
                return i
        return None

    def _fib_zone(self, df: pd.DataFrame) -> tuple:
        sh = df['high'].rolling(20).max().iloc[-20:].max()
        sl = df['low'].rolling(20).min().iloc[-20:].min()
        fib_50 = sl + (sh - sl) * 0.5
        current = df['close'].iloc[-1]
        return ('PAHALILIK' if current > fib_50 else 'UCUZLUK'), fib_50

    def _bias_yon(self, df: pd.DataFrame) -> str:
        if len(df) < 2:
            return 'NEUTRAL'
        return 'BULLISH' if df['close'].iloc[-1] > df['close'].iloc[-2] else 'BEARISH'

    def _sinyal_olustur(self, sembol: str, tf: str, msb, yon: str,
                        alt: float, ust: float, df: pd.DataFrame,
                        idx: int, fib_zone: str, bias_yon: str,
                        s1: bool, s2: bool, s3: bool) -> FVGSinyali:
        son_fiyat  = df['close'].iloc[-1]
        ce_noktasi = (alt + ust) / 2  # Kurumsal limit emri bolgesi
        derinlik   = self._retrace_derinlik(df, alt, ust)
        sart_puan  = sum([s1, s2, s3])

        # Guven skoru - 3 sart ve bolgeden uyuma gore
        guven = 70.0
        guven += sart_puan * 7   # Her sart icin 7 puan
        if derinlik >= 50:  guven += 8
        elif derinlik >= 30: guven += 4
        if (ust - alt) / alt * 100 > 0.5: guven += 5

        # Premium/Discount uyumu (egitim kurali)
        pd_uyum = (yon == 'BULLISH' and fib_zone == 'UCUZLUK') or \
                  (yon == 'BEARISH' and fib_zone == 'PAHALILIK')
        if pd_uyum:  guven += 10
        if bias_yon in ('BULLISH', 'BEARISH') and \
           ((yon == 'BULLISH' and bias_yon == 'BULLISH') or
            (yon == 'BEARISH' and bias_yon == 'BEARISH')):
            guven += 5

        guven      = min(guven, 100.0)
        super_model = guven >= 95 and sart_puan == 3

        if yon == 'BULLISH':
            entry   = ce_noktasi
            sl      = alt * 0.995
            tp1, tp2, tp3 = ust * 1.01, ust * 1.02, ust * 1.03
        else:
            entry   = ce_noktasi
            sl      = ust * 1.005
            tp1, tp2, tp3 = alt * 0.99, alt * 0.98, alt * 0.97

        logger.info(
            f"FVG {yon}: {sembol} {tf} - "
            f"%{guven:.0f} Sartlar:{sart_puan}/3 Super:{super_model}"
        )

        return FVGSinyali(
            sembol       = sembol,
            zaman_dilimi = tf,
            tespit_tarihi = datetime.now(),
            fiyat        = son_fiyat,
            yon          = yon,
            msb_seviye   = getattr(msb, 'kirilma_seviyesi', 0),
            msb_tarih    = getattr(msb, 'tespit_tarihi', datetime.now()),
            fvg_bolgesi  = (alt, ust),
            fvg_derinlik = derinlik,
            guven_skoru  = guven,
            entry_fiyat  = entry,
            stop_loss    = sl,
            take_profit  = [tp1, tp2, tp3],
            fib_zone     = fib_zone,
            bias_yon     = bias_yon,
            crt_confluence = False,
            super_model  = super_model,
            ce_noktasi   = ce_noktasi,
            sart_1_msb   = s1,
            sart_2_bosluk = s2,
            sart_3_hacim = s3,
            sart_puan    = sart_puan,
            bias_pd_uyumu = pd_uyum,
        )

    def _retrace_derinlik(self, df: pd.DataFrame,
                          alt: float, ust: float) -> float:
        son = df['close'].iloc[-1]
        tol = 0.002
        if alt * (1 - tol) <= son <= ust * (1 + tol):
            rng = ust - alt
            return (son - alt) / rng * 100 if rng > 0 else 0
        return 0.0


fvg_detector = FVGDetector()
