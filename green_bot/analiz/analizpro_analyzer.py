import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
import config

# Veri
from veri.veri_topla import veri_topla

# Price Action
from sinyaller.msb_detector import msb_detector, MSBSinyali
from sinyaller.fvg_detector import fvg_detector, FVGSinyali
from sinyaller.ob_detector import ob_detector

# ICT
from ict.bias_detector import bias_detector

# CRT
from crt.crt_detector import crt_detector

# Bot
from bot.telegram_bot import telegram_bot

logger = logging.getLogger(__name__)


class ProAnalyzer:

    def __init__(self):
        self.semboller = config.TARGET_SYMBOLS
        self.batch_size = 10
        self.data = {}

    async def veri_topla(self, sembol: str) -> bool:
        tfs = ['1w', '1d', '4h', '1h', '15m']
        for tf in tfs:
            df = await veri_topla.veri_cek_rest(sembol, tf, 200)
            if df.empty:
                logger.warning(f"{sembol} {tf} veri alınamadı")
                return False
            self.data[(sembol, tf)] = df
        return True

    # 🔥 BERKAY SUPER MODEL FİLTRESİ
    def _berkay_super_filter(self, sonuc: Dict) -> Optional[Dict]:
        """90+ winrate sinyallerini filtrele"""
        yapilar = sonuc['yapilar']
        
        # MSB Super Model kontrol
        msb_1h = yapilar.get('msb_1h', [])
        msb_4h = yapilar.get('msb_4h', [])
        
        super_sinyaller = []
        for msb in msb_1h + msb_4h:
            if msb.super_model and msb.guven_skoru >= 90:
                super_sinyaller.append(msb)
        
        if super_sinyaller:
            sonuc['super_model'] = True
            sonuc['best_sinyal'] = super_sinyaller[0]
            return sonuc
        
        # CRT + MSB confluence
        crt_4h = yapilar.get('crt_4h', [])
        if crt_4h and (msb_1h or msb_4h):
            sonuc['super_model'] = True
            return sonuc
        
        return None

    async def analiz_et(self, sembol: str) -> Dict:
        if not await self.veri_topla(sembol): return {}

        sonuc = {
            'sembol': sembol, 'zaman': datetime.now(), 'bias': {},
            'yapilar': {}, 'puan': 0, 'berkay_skoru': 0
        }

        # BIAS
        df_w = self.data.get((sembol, '1w'))
        df_d = self.data.get((sembol, '1d'))
        if df_w and df_d:
            bias_w = bias_detector.analiz_et(df_w)
            bias_d = bias_detector.analiz_et(df_d)
            sonuc['bias'] = {
                'haftalik': bias_w.yon if bias_w else 'NEUTRAL',
                'gunluk': bias_d.yon if bias_d else 'NEUTRAL'
            }

        # 4H ANALİZ
        df_4h = self.data.get((sembol, '4h'))
        if df_4h is not None:
            msb_4h = msb_detector.analiz_et(df_4h, sembol, '4H')
            sonuc['yapilar']['msb_4h'] = msb_4h
            if msb_4h: 
                sonuc['yapilar']['fvg_4h'] = fvg_detector.analiz_et(df_4h, sembol, '4H', msb_4h[0])
            else:
                sonuc['yapilar']['fvg_4h'] = []
            sonuc['yapilar']['ob_4h'] = ob_detector.analiz_et(df_4h, sembol, '4H')
            sonuc['yapilar']['crt_4h'] = crt_detector.analiz_et(df_4h, sembol, '4H')

        # 1H ANALİZ (BERKAY ÖNCELİKLİ)
        df_1h = self.data.get((sembol, '1h'))
        if df_1h is not None:
            msb_1h = msb_detector.analiz_et(df_1h, sembol, '1H')
            sonuc['yapilar']['msb_1h'] = msb_1h
            if msb_1h:
                sonuc['yapilar']['fvg_1h'] = fvg_detector.analiz_et(df_1h, sembol, '1H', msb_1h[0])
            else:
                sonuc['yapilar']['fvg_1h'] = []
            sonuc['yapilar']['crt_1h'] = crt_detector.analiz_et(df_1h, sembol, '1H')

        # CRT Daily
        if df_d is not None:
            sonuc['yapilar']['crt_daily'] = crt_detector.analiz_et(df_d, sembol, '1D')

        # 🔥 BERKAY SUPER SKOR
        sonuc['berkay_skoru'] = self._berkay_skor_hesapla(sonuc['yapilar'])
        sonuc['puan'] = min(sonuc['berkay_skoru'], 100)

        return sonuc

    def _berkay_skor_hesapla(self, yapilar: Dict) -> int:
        """Berkay Super Model skorlama"""
        skor = 0
        
        # MSB Super Model (90+)
        msb_1h = yapilar.get('msb_1h', [])
        msb_4h = yapilar.get('msb_4h', [])
        super_msb = [m for m in msb_1h + msb_4h if m.super_model]
        if super_msb: skor += 40
        
        # CRT confluence
        crt_count = len(yapilar.get('crt_4h', [])) + len(yapilar.get('crt_1h', []))
        if crt_count >= 1: skor += 20
        if crt_count >= 2: skor += 10
        
        # FVG + OB
        if yapilar.get('fvg_4h'): skor += 15
        if yapilar.get('ob_4h'): skor += 10
        
        return skor

    async def tum_coinleri_tara(self):
        tum_sonuclar = []
        for i in range(0, len(self.semboller), self.batch_size):
            batch = self.semboller[i:i+self.batch_size]
            for sembol in batch:
                sonuc = await self.analiz_et(sembol)
                if sonuc['berkay_skoru'] >= 75:  # 🔥 Berkay eşiği
                    super_sonuc = self._berkay_super_filter(sonuc)
                    if super_sonuc:
                        tum_sonuclar.append(super_sonuc)
                        await self.berkay_sinyal_gonder(super_sonuc)
            await asyncio.sleep(3)
        return tum_sonuclar

    # 🔥 BERKAY SNIPER GÖNDER
    async def berkay_sinyal_gonder(self, sonuc: Dict):
        """🔥 A+++ Super Model sinyali"""
        try:
            msb = sonuc.get('best_sinyal') or sonuc['yapilar'].get('msb_1h', [None])[0]
            if not msb: return
            
            await telegram_bot.sinyal_gonder_msb_berkay(msb)
            
            # CRT varsa ek bilgi
            crt_4h = sonuc['yapilar'].get('crt_4h', [])
            if crt_4h:
                await telegram_bot.sinyal_gonder_crt_berkay(crt_4h[0])
                
        except Exception as e:
            logger.error(f"❌ Berkay sinyal hatası: {e}")

    def _yon_bul(self, sonuc: Dict) -> str:
        bullish = 0
        bearish = 0
        for msb_list in [sonuc['yapilar'].get('msb_1h', []), sonuc['yapilar'].get('msb_4h', [])]:
            for msb in msb_list:
                if msb.yon == 'BULLISH': bullish += 1
                else: bearish += 1
        return 'BULLISH' if bullish > bearish else 'BEARISH' if bearish > bullish else 'NEUTRAL'


pro_analyzer = ProAnalyzer()
