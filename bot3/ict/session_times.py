"""
green_bot/ict/session_times.py
Egitim: Overlap en onemli seans. Asya'da islem yapma.
Kill Zone: Spooling saatleri (15:30/16:30/17:00 TR)
"""
from datetime import time, datetime
import logging

logger = logging.getLogger(__name__)


class SessionTimes:
    """ICT Seans Saatleri ve Kalite Skorlari (Turkiye saati)"""

    def __init__(self):
        # Seans saatleri (TR = UTC+3)
        self.asya_bas    = time(1, 0)
        self.asya_bit    = time(10, 0)
        self.londra_bas  = time(10, 0)
        self.londra_bit  = time(19, 0)
        self.ny_bas      = time(15, 30)
        self.ny_bit      = time(22, 0)
        self.overlap_bas = time(15, 30)   # Londra+NY = en guclu
        self.overlap_bit = time(19, 0)

        # Kill Zone'lar (spooling saatleri dahil)
        self.kill_zones = [
            ('Londra Acilis KZ',   time(10,  0), time(12, 0)),
            ('NY 8:30 Spooling',   time(15, 25), time(15, 45)),
            ('NY Acilis KZ',       time(15, 30), time(17, 30)),
            ('NY 9:30 Spooling',   time(16, 25), time(16, 45)),
            ('NY 10:00 Spooling',  time(16, 55), time(17, 15)),
            ('NY Kapanis KZ',      time(20,  0), time(22,  0)),
        ]

        # Spooling pencereleri (algoritmik hareket saatleri)
        self.spooling_windows = [
            ('15:30 Spooling', time(15, 25), time(15, 45)),
            ('16:30 Spooling', time(16, 25), time(16, 45)),
            ('17:00 Spooling', time(16, 55), time(17, 15)),
        ]

    def su_an_ne_seans(self) -> dict:
        now = datetime.now().time()
        overlap = self.overlap_bas <= now <= self.overlap_bit
        ny      = self.ny_bas      <= now <= self.ny_bit
        londra  = self.londra_bas  <= now <= self.londra_bit
        asya    = self.asya_bas    <= now <= self.asya_bit

        # Skor: 0=Asya(islem yapma), 1=Londra/NY, 2=KZ, 3=Overlap(en guclu)
        if overlap:
            skor  = 3
            isim  = 'OVERLAP'
            label = 'Overlap (En Guclu - LDN+NY)'
        elif ny and londra:
            skor  = 2
            isim  = 'OVERLAP_YAKINI'
            label = 'NY+Londra Beraber'
        elif ny:
            skor  = 1
            isim  = 'NEW_YORK'
            label = 'New York Seasi'
        elif londra:
            skor  = 1
            isim  = 'LONDRA'
            label = 'Londra Seasi'
        elif asya:
            skor  = 0
            isim  = 'ASYA'
            label = 'Asya Seasi (islem yapma)'
        else:
            skor  = 0
            isim  = 'KAPALI'
            label = 'Piyasa Kapali'

        # Kill Zone kontrolu
        kz_aktif, kz_adi = self.kill_zone_kontrol(now)

        return {
            'asya':           asya,
            'londra':         londra,
            'new_york':       ny,
            'overlap':        overlap,
            'seans_ismi':     isim,
            'seans_label':    label,
            'kalite_skoru':   skor,
            'kill_zone':      kz_aktif,
            'kill_zone_adi':  kz_adi,
            # Eski arayuz uyumlulugu
            'londra_killzone': londra and time(10, 0) <= now <= time(11, 30),
        }

    def kill_zone_kontrol(self, now: time = None) -> tuple:
        if now is None:
            now = datetime.now().time()
        for isim, bas, bit in self.kill_zones:
            if bas <= now <= bit:
                return True, isim
        return False, None

    def spooling_kontrol(self, now: time = None) -> tuple:
        """Spooling penceresi mi?"""
        if now is None:
            now = datetime.now().time()
        for isim, bas, bit in self.spooling_windows:
            if bas <= now <= bit:
                return True, isim
        return False, None

    def islem_yapilabilir_mi(self) -> tuple:
        """
        Ana filtre: islem yapilabilir mi?
        Pazartesi ve Asya seasi -> HAYIR
        """
        now       = datetime.now()
        seans     = self.su_an_ne_seans()
        pazartesi = now.weekday() == 0
        cuma      = now.weekday() == 4

        if pazartesi:
            return False, 'Pazartesi Fog of War - islem yapma'
        if seans['kalite_skoru'] == 0:
            return False, f"Dusuk kalite seans: {seans['seans_label']}"

        uyari = 'TGIF - Cuma kapanis manipulasyonu dikkat!' if cuma else None
        return True, uyari


session_times = SessionTimes()
