import asyncio
from datetime import datetime, timedelta
import logging
from veritabani import sinyal_db

logger = logging.getLogger(__name__)

class SinyalTakip:
    def __init__(self):
        self.aktif_sinyaller = {}  # {sinyal_id: {sinyal_data, bitis_tarihi}}
    
    def sinyal_ekle(self, sinyal, sinyal_id):
        """Yeni sinyali takibe al"""
        bitis = datetime.now() + timedelta(hours=24)
        
        # Sinyal tipine göre veri hazırla
        if hasattr(sinyal, 'sembol'):  # MSB, FVG, CRT
            self.aktif_sinyaller[sinyal_id] = {
                'sembol': sinyal.sembol,
                'yon': sinyal.yon,
                'entry': sinyal.entry_fiyat,
                'tp1': sinyal.take_profit[0],
                'tp2': sinyal.take_profit[1],
                'tp3': sinyal.take_profit[2],
                'sl': sinyal.stop_loss,
                'bitis': bitis,
                'tp_seviye': 0,
                'son_fiyat': sinyal.entry_fiyat,
                'durum': 'Aktif'
            }
        else:  # MSB+FVG (dict)
            self.aktif_sinyaller[sinyal_id] = {
                'sembol': sinyal['sembol'],
                'yon': sinyal['yon'],
                'entry': sinyal['entry_fiyat'],
                'tp1': sinyal['take_profit'][0],
                'tp2': sinyal['take_profit'][1],
                'tp3': sinyal['take_profit'][2],
                'sl': sinyal['stop_loss'],
                'bitis': bitis,
                'tp_seviye': 0,
                'son_fiyat': sinyal['entry_fiyat'],
                'durum': 'Aktif'
            }
        
        logger.info(f"📝 Sinyal #{sinyal_id} takibe alındı (24 saat)")
    
    async def fiyat_kontrol(self, veri_topla):
        """Tüm aktif sinyalleri kontrol et"""
        silinecekler = []
        
        for sinyal_id, takip in self.aktif_sinyaller.items():
            # Süre doldu mu?
            if datetime.now() > takip['bitis']:
                kar = self._kar_hesapla(takip, takip['son_fiyat'])
                sinyal_db.sinyal_guncelle(sinyal_id, 'İptal', takip['son_fiyat'])
                silinecekler.append(sinyal_id)
                logger.info(f"⏱️ Sinyal #{sinyal_id} süre doldu, kar: %{kar:.2f}")
                continue
            
            # Güncel fiyatı al
            df = await veri_topla.veri_cek_rest(takip['sembol'], '5m', 1)
            if df.empty:
                continue
            
            guncel_fiyat = df['close'].iloc[-1]
            takip['son_fiyat'] = guncel_fiyat
            
            # TP/SL kontrolü
            sonuc = self._kontrol_et(takip, guncel_fiyat, sinyal_id)
            if sonuc:
                silinecekler.append(sinyal_id)
        
        # Temizlik
        for sinyal_id in silinecekler:
            self.aktif_sinyaller.pop(sinyal_id, None)
    
    def _kontrol_et(self, takip, fiyat, sinyal_id):
        if takip['yon'] == 'BULLISH':
            # TP kontrolü
            if takip['tp_seviye'] < 1 and fiyat >= takip['tp1']:
                takip['tp_seviye'] = 1
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP1', fiyat)
                logger.info(f"💰 Sinyal #{sinyal_id} TP1 oldu!")
            
            if takip['tp_seviye'] < 2 and fiyat >= takip['tp2']:
                takip['tp_seviye'] = 2
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP2', fiyat)
                logger.info(f"💰💰 Sinyal #{sinyal_id} TP2 oldu!")
            
            if takip['tp_seviye'] < 3 and fiyat >= takip['tp3']:
                takip['tp_seviye'] = 3
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP3', fiyat)
                logger.info(f"💰💰💰 Sinyal #{sinyal_id} TP3 oldu!")
            
            # SL kontrolü
            if fiyat <= takip['sl']:
                sinyal_db.sinyal_guncelle(sinyal_id, 'SL', fiyat)
                logger.info(f"❌ Sinyal #{sinyal_id} SL oldu!")
                return True
        
        else:  # BEARISH
            # TP kontrolü
            if takip['tp_seviye'] < 1 and fiyat <= takip['tp1']:
                takip['tp_seviye'] = 1
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP1', fiyat)
                logger.info(f"💰 Sinyal #{sinyal_id} TP1 oldu!")
            
            if takip['tp_seviye'] < 2 and fiyat <= takip['tp2']:
                takip['tp_seviye'] = 2
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP2', fiyat)
                logger.info(f"💰💰 Sinyal #{sinyal_id} TP2 oldu!")
            
            if takip['tp_seviye'] < 3 and fiyat <= takip['tp3']:
                takip['tp_seviye'] = 3
                sinyal_db.sinyal_guncelle(sinyal_id, 'TP3', fiyat)
                logger.info(f"💰💰💰 Sinyal #{sinyal_id} TP3 oldu!")
            
            # SL kontrolü
            if fiyat >= takip['sl']:
                sinyal_db.sinyal_guncelle(sinyal_id, 'SL', fiyat)
                logger.info(f"❌ Sinyal #{sinyal_id} SL oldu!")
                return True
        
        return False
    
    def _kar_hesapla(self, takip, fiyat):
        if takip['yon'] == 'BULLISH':
            return ((fiyat - takip['entry']) / takip['entry']) * 100
        else:
            return ((takip['entry'] - fiyat) / takip['entry']) * 100

sinyal_takip = SinyalTakip()