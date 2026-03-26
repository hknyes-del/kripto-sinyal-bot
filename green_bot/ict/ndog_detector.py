"""
green_bot/ict/ndog_detector.py
Egitim:
- NDOG = New Day Opening Gap: 11:59 kapanis ile 12:00 acilis arasi fark
- 5 is gunu icinde dolar
- Cuma gunlu NDOG gecersiz (hafta sonu kapanis manipulasyonu)
"""
import pandas as pd
from datetime import datetime, time, date
import logging

logger = logging.getLogger(__name__)


class NDOGZone:
    def __init__(self, tarih: date, onceki_kapanis: float, sonraki_acilis: float,
                 gap_tip: str, gap_seviye: float, gecersiz: bool = False):
        self.tarih            = tarih
        self.onceki_kapanis   = onceki_kapanis
        self.sonraki_acilis   = sonraki_acilis
        self.gap_tip          = gap_tip         # 'UP' veya 'DOWN'
        self.gap_seviye       = gap_seviye       # CE noktasi (orta)
        self.doldu            = False
        self.gecersiz         = gecersiz         # Cuma ise gecersiz
        self.tespit_zamani    = datetime.now()

    @property
    def buyukluk_pct(self) -> float:
        if self.onceki_kapanis == 0:
            return 0.0
        return abs(self.sonraki_acilis - self.onceki_kapanis) / self.onceki_kapanis * 100


class NDOGDetector:

    def __init__(self):
        self.ndog_saat   = time(12, 0)
        self.onceki_saat = time(11, 59)
        self.min_gap_pct = 0.01   # Min %0.01 gap (cok kucuk gaplar anlamsiz)

    def ndog_bul(self, df: pd.DataFrame) -> list:
        ndog_list = []
        df2 = df.copy()
        df2['gun'] = df2.index.date

        for gun, gun_df in df2.groupby('gun'):
            # Cuma kontrolu (haftanin 4. gunu = Cuma)
            gun_dt = datetime.combine(gun, time(12, 0))
            is_cuma = gun_dt.weekday() == 4

            # 11:59 mumu
            onceki = gun_df.between_time(self.onceki_saat, self.onceki_saat)
            if onceki.empty:
                continue
            onceki_kapanis = onceki.iloc[0]['close']

            # 12:00 mumu
            sonraki = gun_df.between_time(self.ndog_saat, self.ndog_saat)
            if sonraki.empty:
                continue
            sonraki_acilis = sonraki.iloc[0]['open']

            buyukluk = abs(onceki_kapanis - sonraki_acilis)
            if buyukluk < onceki_kapanis * (self.min_gap_pct / 100):
                continue

            gap_tip    = 'UP' if sonraki_acilis > onceki_kapanis else 'DOWN'
            gap_seviye = (onceki_kapanis + sonraki_acilis) / 2

            ndog = NDOGZone(
                tarih          = gun,
                onceki_kapanis = onceki_kapanis,
                sonraki_acilis = sonraki_acilis,
                gap_tip        = gap_tip,
                gap_seviye     = gap_seviye,
                gecersiz       = is_cuma,
            )
            ndog_list.append(ndog)

            durum = "GECERSIZ (Cuma)" if is_cuma else "Gecerli"
            logger.info(
                f"NDOG: {gun} {gap_tip} @ {gap_seviye:.4f} "
                f"({ndog.buyukluk_pct:.3f}%) [{durum}]"
            )

        return ndog_list

    def aktif_ndog_bul(self, df: pd.DataFrame, bak_kac_gun: int = 7) -> list:
        """
        Son N gunde dolmamis, gecerli NDOG'lari dondur.
        Egitim: 5 is gunu icinde dolar.
        """
        tum_ndog = self.ndog_bul(df)
        son_fiyat = df['close'].iloc[-1]
        aktif = []

        for ndog in tum_ndog[-bak_kac_gun:]:
            if ndog.gecersiz:
                continue
            # Doldu mu kontrol
            if ndog.gap_tip == 'UP':
                # UP gap: fiyat gap seviyesinin altina duserse doldu
                ndog.doldu = son_fiyat <= ndog.onceki_kapanis
            else:
                # DOWN gap: fiyat gap seviyesinin ustune cikarsa doldu
                ndog.doldu = son_fiyat >= ndog.onceki_kapanis

            if not ndog.doldu:
                aktif.append(ndog)

        return aktif


ndog_detector = NDOGDetector()
