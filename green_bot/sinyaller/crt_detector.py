import pandas as pd
from datetime import datetime
from typing import List
import logging

# Logger ayarı
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ==========================================================
# CRT SIGNAL MODEL
# ==========================================================

class CRTSinyali:
    """
    Sniper uyumlu CRT sinyali
    sweep_yon:
        UP   = Üst likidite alındı (bearish manipulation)
        DOWN = Alt likidite alındı (bullish manipulation)
    """

    def __init__(
        self,
        sembol: str,
        htf: str,
        parent_tarih,
        parent_high: float,
        parent_low: float,
        sweep_tarih,
        sweep_yon: str,
        sweep_seviye: float
    ):
        self.sembol = sembol
        self.htf = htf
        self.parent_tarih = self._to_datetime(parent_tarih)
        self.parent_high = parent_high
        self.parent_low = parent_low
        self.sweep_tarih = self._to_datetime(sweep_tarih)
        self.sweep_yon = sweep_yon  # "UP" veya "DOWN"
        self.sweep_seviye = sweep_seviye
        self.tespit_zamani = datetime.now()

    def _to_datetime(self, value):
        if isinstance(value, (pd.Timestamp, datetime)):
            return value
        try:
            return pd.to_datetime(value)
        except Exception:
            return datetime.now()

# ==========================================================
# CRT DETECTOR (SNIPER VERSION)
# ==========================================================

class CRTDetector:
    """
    Profesyonel CRT Tespiti
    - Parent candle liquidity referans alınır
    - Minimum sweep mesafesi zorunlu
    - Body reclaim zorunlu
    - Wick dominance şartı var
    """

    def __init__(self):
        self.min_sweep_oran = 0.25        # Parent range'in %25'i kadar geçmeli
        self.min_wick_body_oran = 0.6     # Wick, body'nin en az %60'ı olmalı
        self.min_range_oran = 0.5         # Current range, parent range'in en az %50'si olmalı

    # ------------------------------------------------------

    def analiz_et(self, df: pd.DataFrame, sembol: str, htf_adi: str = "4H") -> List[CRTSinyali]:
        sinyaller: List[CRTSinyali] = []

        if df is None or len(df) < 3:
            return sinyaller

        # Gerekli sütunlar kontrolü
        gerekli_kolonlar = {"open", "close", "high", "low"}
        if not gerekli_kolonlar.issubset(df.columns):
            logger.error(f"{sembol} {htf_adi} CRT: DataFrame kolonları eksik -> {df.columns}")
            return sinyaller

        try:
            parent = df.iloc[-2]
            current = df.iloc[-1]

            parent_high = parent["high"]
            parent_low = parent["low"]
            parent_range = parent_high - parent_low

            current_high = current["high"]
            current_low = current["low"]
            current_open = current["open"]
            current_close = current["close"]
            current_range = current_high - current_low

            # Koruma
            if parent_range <= 0 or current_range <= 0:
                return sinyaller

            # Gürültü azaltma
            if current_range < parent_range * self.min_range_oran:
                return sinyaller

            body_size = abs(current_close - current_open)
            wick_ust = current_high - max(current_open, current_close)
            wick_alt = min(current_open, current_close) - current_low

            min_sweep_miktar = parent_range * self.min_sweep_oran

            # ======================================================
            # 🔴 ÜST SWEEP (Bearish Manipulation)
            # ======================================================
            yukari_sweep = (
                current_high > parent_high and
                (current_high - parent_high) >= min_sweep_miktar and
                current_close < parent_high and               # Body reclaim
                wick_ust >= body_size * self.min_wick_body_oran
            )

            # ======================================================
            # 🟢 ALT SWEEP (Bullish Manipulation)
            # ======================================================
            asagi_sweep = (
                current_low < parent_low and
                (parent_low - current_low) >= min_sweep_miktar and
                current_close > parent_low and                # Body reclaim
                wick_alt >= body_size * self.min_wick_body_oran
            )

            # ======================================================
            # SIGNAL CREATION
            # ======================================================
            if yukari_sweep:
                sinyaller.append(
                    CRTSinyali(
                        sembol=sembol,
                        htf=htf_adi,
                        parent_tarih=parent.name,
                        parent_high=parent_high,
                        parent_low=parent_low,
                        sweep_tarih=current.name,
                        sweep_yon="UP",
                        sweep_seviye=current_high  # SL için kullanılacak
                    )
                )
                logger.info(f"{sembol} {htf_adi} CRT: ÜST likidite alındı @ {current_high:.4f}")

            if asagi_sweep:
                sinyaller.append(
                    CRTSinyali(
                        sembol=sembol,
                        htf=htf_adi,
                        parent_tarih=parent.name,
                        parent_high=parent_high,
                        parent_low=parent_low,
                        sweep_tarih=current.name,
                        sweep_yon="DOWN",
                        sweep_seviye=current_low  # SL için kullanılacak
                    )
                )
                logger.info(f"{sembol} {htf_adi} CRT: ALT likidite alındı @ {current_low:.4f}")

        except Exception as e:
            logger.error(f"CRT analiz hatası {sembol} {htf_adi}: {e}")

        return sinyaller

# ==========================================================
# GLOBAL INSTANCE
# ==========================================================

crt_detector = CRTDetector()
