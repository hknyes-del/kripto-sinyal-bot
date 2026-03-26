"""
green_bot/ict/ce_detector.py
Egitim: CE = Consequent Encroachment
- Uzun igneli mumların govde - igne ucu arasi orta nokta
- Kurumsal limit emirler o noktada atlanir (skip edilir)
- Fiyat CE noktasina geri gelir (pozisyon alma firsati)
- CE = FVG'nin "CE noktasi" ile ayni konsept
"""
import pandas as pd
from datetime import datetime
from typing import List
import logging

logger = logging.getLogger(__name__)


class CEZone:
    def __init__(self, sembol: str, zaman_dilimi: str,
                 igne_ucu: float, govde_kenar: float,
                 orta_nokta: float, tip: str, mum_tarihi: datetime):
        self.sembol       = sembol
        self.zaman_dilimi = zaman_dilimi
        self.igne_ucu     = igne_ucu
        self.govde_kenar  = govde_kenar
        self.orta_nokta   = orta_nokta
        self.tip          = tip           # 'BULLISH_CE' veya 'BEARISH_CE'
        self.mum_tarihi   = mum_tarihi
        self.dolduruldu   = False
        self.tespit_zamani = datetime.now()

    @property
    def uzaklik_pct(self) -> float:
        """Son fiyata gore uzaklik - dinamik kullanim icin."""
        return 0.0


class CEDetector:
    """
    CE Dedektoru - Egitim versiyonu
    Uzun igne orani: ignerin govdeye orani >= 2x (min_igne_orani)
    """

    def __init__(self, min_igne_orani: float = 2.0):
        self.min_igne_orani = min_igne_orani

    def _igne_oran_hesapla(self, mum: pd.Series):
        govde    = abs(mum['close'] - mum['open'])
        igne_ust = mum['high'] - max(mum['close'], mum['open'])
        igne_alt = min(mum['close'], mum['open']) - mum['low']
        if govde == 0:
            return igne_ust, igne_alt, 99
        return igne_ust, igne_alt, (igne_ust + igne_alt) / govde

    def analiz_et(self, df: pd.DataFrame, sembol: str, tf: str) -> List[CEZone]:
        ce_list = []

        for i in range(len(df)):
            mum = df.iloc[i]
            igne_ust, igne_alt, oran = self._igne_oran_hesapla(mum)

            govde = abs(mum['close'] - mum['open'])
            if govde == 0:
                continue

            # Yukari uzun igne (BEARISH CE - fiyat geri gelir)
            if igne_ust / govde >= self.min_igne_orani:
                igne_ucu   = mum['high']
                govde_kenar = max(mum['close'], mum['open'])
                ce_noktasi  = (igne_ucu + govde_kenar) / 2
                ce_list.append(CEZone(
                    sembol      = sembol,
                    zaman_dilimi = tf,
                    igne_ucu    = igne_ucu,
                    govde_kenar = govde_kenar,
                    orta_nokta  = ce_noktasi,
                    tip         = 'BEARISH_CE',
                    mum_tarihi  = df.index[i],
                ))

            # Asagi uzun igne (BULLISH CE - fiyat geri gelir)
            if igne_alt / govde >= self.min_igne_orani:
                igne_ucu    = mum['low']
                govde_kenar = min(mum['close'], mum['open'])
                ce_noktasi  = (igne_ucu + govde_kenar) / 2
                ce_list.append(CEZone(
                    sembol      = sembol,
                    zaman_dilimi = tf,
                    igne_ucu    = igne_ucu,
                    govde_kenar = govde_kenar,
                    orta_nokta  = ce_noktasi,
                    tip         = 'BULLISH_CE',
                    mum_tarihi  = df.index[i],
                ))

        logger.debug(f"CE bulundu: {len(ce_list)} adet ({sembol} {tf})")
        return ce_list

    def en_yakin_ce(self, ce_list: List[CEZone], fiyat: float,
                    direction: str) -> CEZone:
        """Mevcut fiyata en yakin uyumlu CE noktasini dondur."""
        uyumlu = [
            c for c in ce_list
            if (direction == 'LONG'  and c.tip == 'BULLISH_CE') or
               (direction == 'SHORT' and c.tip == 'BEARISH_CE')
        ]
        if not uyumlu:
            return None
        return min(uyumlu, key=lambda c: abs(c.orta_nokta - fiyat))


ce_detector = CEDetector()
