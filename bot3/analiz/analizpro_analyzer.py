import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

# Veri
from veri.veri_topla import veri_topla

# Price Action
from sinyaller.msb_detector import msb_detector, MSBSinyali
from sinyaller.fvg_detector import fvg_detector, FVGSinyali
from sinyaller.ob_detector import ob_detector, OrderBlock
from sinyaller.breaker_detector import breaker_detector, BreakerZone
from sinyaller.mitigation_detector import mitigation_detector, MitigationZone
from sinyaller.imbalance_detector import imbalance_detector, ImbalanceZone
from sinyaller.ote_detector import ote_detector, OTEZone
from sinyaller.amd_detector import amd_detector, AMDZone

# ICT
from ict.session_times import session_times
from ict.bias_detector import bias_detector
from ict.rel_detector import rel_detector, RELZone
from ict.judas_swing import judas_detector
from ict.silver_bullet import silver_bullet_detector, SilverBulletZone
from ict.ndog_detector import ndog_detector, NDOGZone
from ict.pd_array import pd_array_detector, PDArray
from ict.ce_detector import ce_detector, CEZone
from ict.spooling_detector import spooling_detector, SpoolingZone
from ict.tgif_detector import tgif_detector, TGIFZone

# CRT
from crt.parent_candle import parent_candle_detector, ParentCandle
from crt.crt_detector import crt_detector, CRTSinyali
from crt.monday_range import monday_range_detector, MondayRange
from crt.smt_detector import smt_detector, SMTUyumsuzluk
from crt.a_plus_setup import a_plus_detector, APlusSetup

# Bot
from bot.telegram_bot import telegram_bot
from veritabani import sinyal_db

logger = logging.getLogger(__name__)

class ProAnalyzer:
    """
    Profesyonel Analiz Sistemi
    - Tüm yapıları tarar
    - Confluence hesaplar
    - Setup puanlar
    - En kaliteli sinyalleri üretir
    """
    
    def __init__(self):
        self.semboller = config.TARGET_SYMBOLS
        self.coin_index = 0
        self.batch_size = 10
        
        # Veri havuzu
        self.data = {}  # {(sembol, tf): df}
        
        # Yapı havuzu
        self.yapilar = {
            'msb': [],
            'fvg': [],
            'ob': [],
            'breaker': [],
            'mitigation': [],
            'imbalance': [],
            'ote': [],
            'amd': [],
            'rel': [],
            'judas': [],
            'silver': [],
            'ndog': [],
            'pd': [],
            'ce': [],
            'spooling': [],
            'tgif': [],
            'crt': [],
            'monday': [],
            'smt': [],
            'aplus': []
        }
    
    async def veri_topla(self, sembol: str) -> bool:
        """Tüm zaman dilimlerinde veri topla"""
        tfs = ['1w', '1d', '4h', '1h', '15m']
        
        for tf in tfs:
            df = await veri_topla.veri_cek_rest(sembol, tf, 200)
            if df.empty:
                logger.warning(f"⚠️ {sembol} {tf} veri alınamadı")
                return False
            self.data[(sembol, tf)] = df
        
        return True
    
    async def analiz_et(self, sembol: str) -> Dict:
        """Tüm yapıları analiz et"""
        
        if not await self.veri_topla(sembol):
            return {}
        
        sonuc = {
            'sembol': sembol,
            'zaman': datetime.now(),
            'bias': {},
            'yapilar': {},
            'setuplar': [],
            'puan': 0
        }
        
        # 1. BIAS ANALİZİ
        df_w = self.data.get((sembol, '1w'))
        df_d = self.data.get((sembol, '1d'))
        
        if df_w is not None and df_d is not None:
            sonuc['bias'] = {
                'haftalik': bias_detector.haftalik_bias(df_w),
                'gunluk': bias_detector.gunluk_bias(df_d),
                'pahali_ucuz': self._pahali_ucuz_kontrol(df_d)
            }
        
        # 2. YAPI TESPİTİ
        # Price Action
        df_4h = self.data.get((sembol, '4h'))
        df_1h = self.data.get((sembol, '1h'))
        df_15m = self.data.get((sembol, '15m'))
        
        if df_4h is not None:
            sonuc['yapilar']['msb_4h'] = msb_detector.analiz_et(df_4h, sembol, '4H')
            sonuc['yapilar']['fvg_4h'] = fvg_detector.analiz_et(df_4h, sembol, '4H', [], [], [])
            sonuc['yapilar']['ob_4h'] = ob_detector.analiz_et(df_4h, sembol, '4H')
        
        if df_1h is not None:
            sonuc['yapilar']['msb_1h'] = msb_detector.analiz_et(df_1h, sembol, '1H')
            sonuc['yapilar']['fvg_1h'] = fvg_detector.analiz_et(df_1h, sembol, '1H', [], [], [])
            sonuc['yapilar']['amd'] = amd_detector.analiz_et(df_1h, sembol, '1H')
            sonuc['yapilar']['ote'] = ote_detector.analiz_et(df_1h, sembol, '1H')
        
        # ICT
        if df_1h is not None:
            sonuc['yapilar']['rel'] = rel_detector.analiz_et(df_1h, sembol)
            sonuc['yapilar']['judas'] = judas_detector.analiz_et(df_1h, sembol)
            sonuc['yapilar']['silver'] = silver_bullet_detector.analiz_et(df_1h, sembol)
            sonuc['yapilar']['ndog'] = ndog_detector.ndog_bul(df_1h)
            sonuc['yapilar']['ce'] = ce_detector.analiz_et(df_1h, sembol, '1H')
        
        # CRT
        if df_d is not None and df_4h is not None:
            sonuc['yapilar']['crt_daily'] = crt_detector.analiz_et(df_d, sembol, '1D', [], [], [])
            sonuc['yapilar']['crt_4h'] = crt_detector.analiz_et(df_4h, sembol, '4H', [], [], [])
            sonuc['yapilar']['monday'] = monday_range_detector.analiz_et(df_4h, sembol)
        
        # 3. A++ SETUP ARA
        if df_w is not None and df_d is not None and df_4h is not None:
            # Korele parite için ETH (BTC için)
            korele_sembol = 'ETHUSDT' if 'BTC' in sembol else 'BTCUSDT'
            df_korele = self.data.get((korele_sembol, '4h'))
            
            if df_korele is not None:
                aplus = a_plus_detector.analiz_et(
                    df_w, df_d, df_4h, sembol,
                    df_korele, korele_sembol,
                    [], [], []
                )
                sonuc['yapilar']['aplus'] = aplus
                sonuc['setuplar'].extend(aplus)
        
        # 4. PUAN HESAPLA
        sonuc['puan'] = self._puan_hesapla(sonuc['yapilar'])
        
        return sonuc
    
    def _pahali_ucuz_kontrol(self, df: pd.DataFrame) -> str:
        """Fiyat pahalı mı ucuz mu?"""
        son_20 = df.iloc[-20:]
        dip = son_20['low'].min()
        tepe = son_20['high'].max()
        orta = (dip + tepe) / 2
        son_fiyat = df['close'].iloc[-1]
        
        if son_fiyat > orta * 1.1:
            return 'COK PAHALI'
        elif son_fiyat > orta:
            return 'PAHALI'
        elif son_fiyat < orta * 0.9:
            return 'COK UCUZ'
        elif son_fiyat < orta:
            return 'UCUZ'
        else:
            return 'NORMAL'
    
    def _puan_hesapla(self, yapilar: Dict) -> int:
        """Setup puanını hesapla (0-100)"""
        puan = 0
        
        # MSB varlığı
        if len(yapilar.get('msb_4h', [])) > 0:
            puan += 10
        if len(yapilar.get('msb_1h', [])) > 0:
            puan += 5
        
        # FVG varlığı
        if len(yapilar.get('fvg_4h', [])) > 0:
            puan += 10
        if len(yapilar.get('fvg_1h', [])) > 0:
            puan += 5
        
        # Order Block
        if len(yapilar.get('ob_4h', [])) > 0:
            puan += 10
        
        # ICT yapıları
        if len(yapilar.get('judas', [])) > 0:
            puan += 15
        if len(yapilar.get('silver', [])) > 0:
            puan += 20
        if len(yapilar.get('ndog', [])) > 0:
            puan += 10
        
        # CRT yapıları
        if len(yapilar.get('crt_daily', [])) > 0:
            puan += 15
        if len(yapilar.get('crt_4h', [])) > 0:
            puan += 10
        if len(yapilar.get('monday', [])) > 0:
            puan += 15
        
        # A++ Setup
        if len(yapilar.get('aplus', [])) > 0:
            puan += 25
        
        return min(puan, 100)
    
    async def tum_coinleri_tara(self):
        """Tüm coinleri tara"""
        tum_sonuclar = []
        
        for i in range(0, len(self.semboller), self.batch_size):
            batch = self.semboller[i:i+self.batch_size]
            
            for sembol in batch:
                sonuc = await self.analiz_et(sembol)
                if sonuc and sonuc['puan'] >= 60:  # Sadece 60+ puanlıları bildir
                    tum_sonuclar.append(sonuc)
                    await self.sinyal_gonder(sonuc)
            
            await asyncio.sleep(5)  # Rate limit koruması
        
        return tum_sonuclar
    
    async def sinyal_gonder(self, sonuc: Dict):
        """Analiz sonucunu Telegram'a gönder"""
        try:
            # Sinyal ID
            sinyal_id = len(self.yapilar['msb']) + 1
            
            # Mesaj oluştur
            yon = self._yon_bul(sonuc)
            emoji = "🟢" if yon == 'BULLISH' else "🔴" if yon == 'BEARISH' else "⚪"
            
            mesaj = f"""
🔥 *PROFESYONEL ANALİZ* 🔥

💰 *{sonuc['sembol']}*
⭐ Puan: {sonuc['puan']}/100 {emoji}

📊 *BİAS*
• Haftalık: {sonuc['bias'].get('haftalik', 'N/A')}
• Günlük: {sonuc['bias'].get('gunluk', 'N/A')}
• Bölge: {sonuc['bias'].get('pahali_ucuz', 'N/A')}

🎯 *TESPİT EDİLEN YAPILAR*
"""
            # Yapıları ekle
            for tip, liste in sonuc['yapilar'].items():
                if len(liste) > 0:
                    mesaj += f"• {tip.upper()}: {len(liste)} adet\n"
            
            mesaj += f"""
⏰ {sonuc['zaman'].strftime('%d.%m.%Y %H:%M')}

#PRO #{sonuc['sembol'].replace('/', '')}
"""
            
            # Telegram'a gönder
            await telegram_bot.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=mesaj,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Profesyonel analiz gönderildi: {sonuc['sembol']} (puan:{sonuc['puan']})")
            
        except Exception as e:
            logger.error(f"❌ Analiz gönderilemedi: {e}")
    
    def _yon_bul(self, sonuc: Dict) -> str:
        """Analizden genel yönü bul"""
        bullish = 0
        bearish = 0
        
        # MSB yönleri
        for msb in sonuc['yapilar'].get('msb_4h', []):
            if msb.yon == 'BULLISH':
                bullish += 1
            else:
                bearish += 1
        
        # CRT yönleri
        for crt in sonuc['yapilar'].get('crt_4h', []):
            if crt.manipulasyon_yonu == 'LOW':
                bullish += 2
            else:
                bearish += 2
        
        if bullish > bearish:
            return 'BULLISH'
        elif bearish > bullish:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

pro_analyzer = ProAnalyzer()