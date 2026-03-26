"""
green_bot/ict/spooling_detector.py
Egitim: Spooling = algoritmik tek mumlu ani hareket.
15:30 / 16:30 / 17:00 TR saatlerinde olur.
Gövde 3x ortalama > spooling mumudur.
"""
import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SpoolingZone:
    def __init__(self, sembol: str, saat_araligi: str, hareket_yonu: str,
                 hareket_buyuklugu: float, baslangic_tarih: datetime,
                 spooling_mum: bool = False):
        self.sembol          = sembol
        self.saat_araligi    = saat_araligi
        self.hareket_yonu    = hareket_yonu        # 'UP' / 'DOWN'
        self.hareket_buyuklugu = hareket_buyuklugu  # %
        self.baslangic_tarih = baslangic_tarih
        self.spooling_mum    = spooling_mum         # Tek mum spooling mi?
        self.tespit_zamani   = datetime.now()


class SpoolingDetector:
    """
    Spooling Dedektoru - Egitim Versiyonu
    - NY acilis (08:30 NY = 15:30 TR): en guclu spooling
    - NY 09:30 (16:30 TR): ikinci guclu
    - NY 10:00 (17:00 TR): ucuncu
    - Tek mumda govde 3x ortalama -> spooling mumu
    - Yön: trend tersine ise sahte kirilim (geri don beklenir)
    """

    def __init__(self):
        self.spooling_windows = [
            ('15:30 NY 8:30',  time(15, 25), time(15, 45)),
            ('16:30 NY 9:30',  time(16, 25), time(16, 45)),
            ('17:00 NY 10:00', time(16, 55), time(17, 15)),
        ]
        self.min_hareket_pct = 0.8  # Min %0.8 hareket (eskiden %1.0, daha hassas)

    def _govde_buyuklugu(self, mum: pd.Series) -> float:
        return abs(mum['close'] - mum['open'])

    def _spooling_mum_mu(self, df: pd.DataFrame, idx: int) -> bool:
        """
        Spooling mumu tespiti: govde 3x ortalama govde buyuklugu mu?
        Egitim: Algoritmik tek mumlu ani hareket = spooling.
        """
        if idx < 10:
            return False
        son_gövdeler = [self._govde_buyuklugu(df.iloc[i]) for i in range(idx-10, idx)]
        ort_govde = np.mean(son_gövdeler) if son_gövdeler else 0
        if ort_govde == 0:
            return False
        bu_govde = self._govde_buyuklugu(df.iloc[idx])
        return bu_govde > ort_govde * 3

    def analiz_et(self, df: pd.DataFrame, sembol: str) -> List[SpoolingZone]:
        spooling_list = []

        for aralik_adi, bas_saat, bit_saat in self.spooling_windows:
            try:
                bugun = df.index[-1].date()
                bas   = datetime.combine(bugun, bas_saat)
                bit   = datetime.combine(bugun, bit_saat)

                aralik_df = df[(df.index >= bas) & (df.index <= bit)]
                if len(aralik_df) < 1:
                    continue

                bas_fiyat = aralik_df.iloc[0]['open']
                son_fiyat = aralik_df.iloc[-1]['close']

                if bas_fiyat == 0:
                    continue

                hareket = abs(son_fiyat - bas_fiyat) / bas_fiyat * 100

                # Tek mumlu hizli hareket (spooling mumu kontrolu)
                spooling_mum = False
                if len(aralik_df) <= 3:
                    for i, (idx, row) in enumerate(aralik_df.iterrows()):
                        df_idx = df.index.get_loc(idx)
                        if self._spooling_mum_mu(df, df_idx):
                            spooling_mum = True
                            break

                if hareket > self.min_hareket_pct or spooling_mum:
                    yon = 'UP' if son_fiyat > bas_fiyat else 'DOWN'
                    spooling_list.append(SpoolingZone(
                        sembol            = sembol,
                        saat_araligi      = aralik_adi,
                        hareket_yonu      = yon,
                        hareket_buyuklugu = hareket,
                        baslangic_tarih   = bas,
                        spooling_mum      = spooling_mum,
                    ))
                    logger.info(
                        f"Spooling: {sembol} - {aralik_adi} - {yon} "
                        f"(%{hareket:.2f}) Tek mum: {spooling_mum}"
                    )
            except Exception as e:
                logger.debug(f"Spooling pencere hatasi {aralik_adi}: {e}")

        return spooling_list


spooling_detector = SpoolingDetector()
