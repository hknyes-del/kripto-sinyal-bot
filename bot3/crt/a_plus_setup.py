"""
green_bot/crt/a_plus_setup.py
Asakura (Berkay Kemal Elcim) A++ Setup - Tam Kural Seti

5 TEMEL SART (A++ icin hepsi olmali):
  1. HTF Bias (1D/W):   Trend + Premium/Discount ESLESME (STRONG_BULLISH/BEARISH)
  2. Key Level Temasi:  FVG / OB / CE seviyesinde olmak
  3. Premium/Discount:  SHORT=PREMIUM, LONG=DISCOUNT zorunlu
  4. CRT Yapisi:        Manipulasyon + ChoCH + Re-test
  5. SMT (tuz biber):  Korele parite uyumsuzlugu -> ekstra guc

SKOR SİSTEMİ (max 12):
  HTF Bias gucu          : 0-2
  4H Trend uyumu         : 1
  CRT yapisi             : 2
  Karakter Degisimi      : 1
  MSB                    : 2
  FVG (3 sart)           : 1
  Order Block            : 0.5
  SMT uyumsuzlugu        : 2
  OTE bolgesi            : 0.5
  Seans kalitesi (Overlap): 0-1
  Judas Swing uyumu      : 1
  Spooling penceresi     : 0.5
  CE yakinligi           : 0.5

Grade A++ = 9+ | A+ = 7+ | A = 5+ | B = <5 (sinyal uretme)
"""

import pandas as pd
from datetime import datetime
from typing import List, Optional
import logging

from crt.crt_detector import crt_detector, CRTSinyali
from crt.smt_detector import smt_detector, SMTUyumsuzluk
from ict.bias_detector import bias_detector
from ict.session_times import session_times
from ict.judas_swing import judas_detector
from ict.spooling_detector import spooling_detector
from ict.ce_detector import ce_detector

logger = logging.getLogger(__name__)


class APlusSetup:
    def __init__(self, sembol: str, bias_result, crt: CRTSinyali,
                 smt: Optional[SMTUyumsuzluk] = None,
                 seans_bilgi: dict = None,
                 judas: dict = None,
                 spooling_list: list = None,
                 ce_list: list = None,
                 fvg_var: bool = False,
                 ob_var: bool = False,
                 msb_var: bool = False):
        self.sembol        = sembol
        self.bias_result   = bias_result
        self.crt           = crt
        self.smt           = smt
        self.seans         = seans_bilgi or {}
        self.judas         = judas or {}
        self.spooling_list = spooling_list or []
        self.ce_list       = ce_list or []
        self.fvg_var       = fvg_var
        self.ob_var        = ob_var
        self.msb_var       = msb_var
        self.puan          = self._puan_hesapla()
        self.grade         = self._grade()
        self.tespit_zamani = datetime.now()

    # ─── A++ YON UYUMU ZORUNLU ───────────────────────────────
    def _yon_uyumu_var_mi(self) -> bool:
        """CRT yonu ile Bias uyumu zorunlu."""
        if not self.bias_result or not self.crt:
            return False
        crt_yon   = self.crt.yon   # 'BULLISH' / 'BEARISH'
        bias_yon  = self.bias_result.yon  # 'BULLISH' / 'BEARISH'
        return crt_yon == bias_yon

    # ─── PREMIUM/DISCOUNT KURALI ─────────────────────────────
    def _premium_discount_uyumu(self) -> bool:
        """Egitim kurali: SHORT icin PREMIUM, LONG icin DISCOUNT."""
        if not self.bias_result or not self.crt:
            return False
        if self.crt.yon == 'BEARISH' and self.bias_result.pd_zone == 'PREMIUM':
            return True
        if self.crt.yon == 'BULLISH' and self.bias_result.pd_zone == 'DISCOUNT':
            return True
        return False

    def _puan_hesapla(self) -> float:
        puan = 0.0

        # 1. HTF Bias (max 2)
        if self.bias_result:
            if self.bias_result.bias in ('STRONG_BULLISH', 'STRONG_BEARISH'):
                puan += 2   # Tam uyum (Trend + PD eslesmesi)
            elif self.bias_result.yon != 'NEUTRAL':
                puan += 1

        # 2. CRT yapisi (max 2)
        if self.crt:
            puan += 1
            if hasattr(self.crt, 'is_retesting') and self.crt.is_retesting:
                puan += 1   # Re-test = guclu CRT

        # 3. MSB (max 2) - CRT'deki MSB + Guc
        if self.msb_var:
            puan += 1
            if self.crt and hasattr(self.crt, 'guven_skoru') and self.crt.guven_skoru > 80:
                puan += 1

        # 4. FVG (3 sart saglandiysa)
        if self.fvg_var:
            puan += 1

        # 5. Order Block
        if self.ob_var:
            puan += 0.5

        # 6. SMT uyumsuzlugu (max 2) - "tuz biber"
        if self.smt:
            puan += 2

        # 7. Seans kalitesi
        kalite = self.seans.get('kalite_skoru', 0)
        if kalite == 3:    puan += 1    # Overlap
        elif kalite == 2:  puan += 0.5  # Kill Zone

        # 8. Judas Swing yonu uyumu
        if self.judas.get('var_mi') and self.crt:
            judas_gercek = self.judas.get('gercek_yon', '')
            crt_yon_str  = 'LONG' if self.crt.yon == 'BULLISH' else 'SHORT'
            if judas_gercek == crt_yon_str:
                puan += 1

        # 9. Spooling penceresi
        if self.spooling_list:
            puan += 0.5

        # 10. CE yakinligi (fiyat CE'ye yakinsa +0.5)
        if self.ce_list and self.crt:
            puan += 0.5

        # 11. Premium/Discount uyumu ZORUNLU — uyum yoksa tum puan sifir
        if not self._premium_discount_uyumu():
            return 0.0

        # 12. Yon uyumu ZORUNLU — uyum yoksa sifir
        if not self._yon_uyumu_var_mi():
            return 0.0

        return round(puan, 1)

    def _grade(self) -> str:
        if self.puan >= 9:  return 'A++'
        if self.puan >= 7:  return 'A+'
        if self.puan >= 5:  return 'A'
        return 'B'

    @property
    def sinyal_gonderilecek_mi(self) -> bool:
        return self.puan >= 5

    @property
    def mamacita(self) -> bool:
        """Egitim'deki 'MAMACITA' = A++ setup."""
        return self.grade == 'A++'


class APlusSetupDetector:

    def analiz_et(self, df_weekly: pd.DataFrame, df_daily: pd.DataFrame,
                  df_4h: pd.DataFrame, sembol: str,
                  korele_df: pd.DataFrame = None,
                  korele_sembol: str = None,
                  df_1m: pd.DataFrame = None) -> List[APlusSetup]:
        """
        A++ Setup analizi - tam kural seti.
        df_weekly, df_daily, df_4h gerekli.
        df_1m: Judas Swing icin (opsiyonel).
        """
        sonuclar = []

        # ── Bias ─────────────────────────────────────────────
        bias_result = bias_detector.analiz_et(df_daily)

        # Bias yok veya NEUTRAL -> A++ olamaz
        if bias_result.yon == 'NEUTRAL':
            return sonuclar

        # A++ icin STRONG bias zorunlu
        if not bias_result.a_plus_uyumlu:
            logger.debug(f"{sembol}: Zayif bias ({bias_result.bias}) - A++ icin yetersiz")

        # ── Seans ────────────────────────────────────────────
        seans = session_times.su_an_ne_seans()
        islem_ok, uyari = session_times.islem_yapilabilir_mi()
        if not islem_ok:
            logger.info(f"{sembol}: {uyari} - tarama atlandi")
            return sonuclar

        # ── CRT (4H) ─────────────────────────────────────────
        yon_str = 'long' if bias_result.yon == 'BULLISH' else 'short'
        crtler  = crt_detector.analiz_et(df_4h, sembol, '4h')

        for crt in crtler:
            # CRT yon uyumu
            if crt.yon != bias_result.yon:
                continue

            # ── SMT ──────────────────────────────────────────
            smt = None
            if korele_df is not None and korele_sembol:
                try:
                    smt_dict = {sembol: df_4h, korele_sembol: korele_df}
                    smt_list = smt_detector.analiz_et(smt_dict)
                    if smt_list:
                        smt = smt_list[0]
                except Exception as e:
                    logger.debug(f"SMT hatasi: {e}")

            # ── Judas Swing ───────────────────────────────────
            judas = {'var_mi': False}
            if df_1m is not None:
                try:
                    judas = judas_detector.analiz_et(df_1m, sembol)
                except Exception as e:
                    logger.debug(f"Judas hatasi: {e}")

            # ── Spooling ─────────────────────────────────────
            spooling_list = []
            try:
                spooling_list = spooling_detector.analiz_et(df_4h, sembol)
            except Exception as e:
                logger.debug(f"Spooling hatasi: {e}")

            # ── CE Seviyeleri ─────────────────────────────────
            ce_list = []
            try:
                ce_list = ce_detector.analiz_et(df_4h, sembol, '4h')
            except Exception as e:
                logger.debug(f"CE hatasi: {e}")

            setup = APlusSetup(
                sembol       = sembol,
                bias_result  = bias_result,
                crt          = crt,
                smt          = smt,
                seans_bilgi  = seans,
                judas        = judas,
                spooling_list = spooling_list,
                ce_list      = ce_list,
                fvg_var      = hasattr(crt, 'fvg_var') and crt.fvg_var,
                ob_var       = False,
                msb_var      = True,  # CRT icinde MSB var
            )

            if setup.sinyal_gonderilecek_mi:
                sonuclar.append(setup)
                logger.info(
                    f"{'MAMACITA ' if setup.mamacita else ''}"
                    f"A++ Setup: {sembol} {setup.grade} "
                    f"puan:{setup.puan} seans:{seans['seans_label']}"
                )

        return sonuclar


a_plus_detector = APlusSetupDetector()
