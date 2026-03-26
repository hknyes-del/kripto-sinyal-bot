"""
green_bot/ict/judas_swing.py
Egitim: Judas Swing = Asya range'ini killit, Londra'da geri don.
- Asya (01:00-10:00 TR) range belirlenir
- Londra Kill Zone (10:00-11:30) range'in bir tarafini sweep eder
- Fiyat range icine geri donerse GERCEK YON = diger taraf
- Yani asya YUKSELIYOR gibi gorunup dusuyorsa -> SHORT
"""
import pandas as pd
from datetime import datetime, time
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class JudasSwingDetector:

    def __init__(self):
        self.asya_bas    = time(1, 0)
        self.asya_bit    = time(10, 0)
        self.kz_bas      = time(10, 0)
        self.kz_bit      = time(11, 30)
        self.tolerans    = 0.001   # %0.1 tolerans

    def analiz_et(self, df_1m: pd.DataFrame, sembol: str) -> Dict:
        sonuc = {
            'var_mi':       False,
            'yon':          None,   # 'YUKARI_ALDATMA' veya 'ASAGI_ALDATMA'
            'gercek_yon':   None,   # Beklenen gercek hareket yonu
            'sweep_seviye': None,
            'tokyo_dip':    None,
            'tokyo_tepe':   None,
            'hedef':        None,
        }

        if df_1m is None or df_1m.empty:
            return sonuc

        try:
            # Asya range
            asya_df = df_1m.between_time(self.asya_bas, self.asya_bit)
            if asya_df.empty:
                return sonuc

            asya_dip   = asya_df['low'].min()
            asya_tepe  = asya_df['high'].max()
            asya_range = asya_tepe - asya_dip

            if asya_range <= 0:
                return sonuc

            # Londra Kill Zone
            kz_df = df_1m.between_time(self.kz_bas, self.kz_bit)
            if kz_df.empty:
                return sonuc

            # Alt sweep -> Yukari Aldatma (Judas asal arama yonu: SHORT pozisyon kurma)
            # Sweep + geri donus varsa -> LONG beklenir (gercek yon YUKARI)
            if kz_df['low'].min() < asya_dip * (1 - self.tolerans):
                # Sweep oldu, simdi geri dondu mu?
                kz_son = kz_df.iloc[-1]['close']
                if kz_son > asya_dip:
                    sonuc.update({
                        'var_mi':       True,
                        'yon':          'ASAGI_ALDATMA',
                        'gercek_yon':   'LONG',
                        'sweep_seviye': kz_df['low'].min(),
                        'tokyo_dip':    asya_dip,
                        'tokyo_tepe':   asya_tepe,
                        'hedef':        asya_tepe,
                    })
                    logger.info(f"Judas Swing (LONG): {sembol} - Alt sweep sonrasi yukari")
                    return sonuc

            # Ust sweep -> Asagi Aldatma
            # Sweep + geri donus varsa -> SHORT beklenir (gercek yon ASAGI)
            if kz_df['high'].max() > asya_tepe * (1 + self.tolerans):
                kz_son = kz_df.iloc[-1]['close']
                if kz_son < asya_tepe:
                    sonuc.update({
                        'var_mi':       True,
                        'yon':          'YUKARI_ALDATMA',
                        'gercek_yon':   'SHORT',
                        'sweep_seviye': kz_df['high'].max(),
                        'tokyo_dip':    asya_dip,
                        'tokyo_tepe':   asya_tepe,
                        'hedef':        asya_dip,
                    })
                    logger.info(f"Judas Swing (SHORT): {sembol} - Ust sweep sonrasi asagi")
                    return sonuc

        except Exception as e:
            logger.debug(f"Judas Swing hatasi {sembol}: {e}")

        return sonuc


judas_detector = JudasSwingDetector()
