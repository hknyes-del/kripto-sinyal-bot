import asyncio
import pandas as pd
from datetime import datetime, timedelta
import logging
from tabulate import tabulate

from veri.veri_topla import veri_topla
from sinyaller.msb_detector import msb_detector
from sinyaller.fvg_retrace import fvg_detector
from sinyaller.crt_detector import crt_detector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Backtest:
    def __init__(self, sembol='BTC/USDT', gun=30, zaman_dilimi='1h'):
        self.sembol = sembol
        self.gun = gun
        self.zaman_dilimi = zaman_dilimi
        self.df = None
        self.sonuclar = {
            'MSB': {'toplam': 0, 'basarili': 0, 'basarisiz': 0},
            'FVG': {'toplam': 0, 'basarili': 0, 'basarisiz': 0},
            'CRT': {'toplam': 0, 'basarili': 0, 'basarisiz': 0},
        }
        self.tum_sinyaller = []

    async def veri_cek(self):
        """Son X günlük veriyi çek"""
        logger.info(f"📥 {self.sembol} için {self.zaman_dilimi} verisi çekiliyor...")
        df = await veri_topla.veri_cek_rest(self.sembol, self.zaman_dilimi, limit=500)
        
        if df.empty:
            logger.error("❌ Veri çekilemedi!")
            return False
            
        # Son X günü al
        bitis = df.index[-1]
        baslangic = bitis - timedelta(days=self.gun)
        df = df[df.index >= baslangic]
        
        logger.info(f"✅ {len(df)} mum alındı ({df.index[0].date()} - {df.index[-1].date()})")
        self.df = df
        return True

    def _sinyal_bul(self, dedektor, tip):
        """Veri üzerinde sinyal ara"""
        sinyaller = []
        
        for i in range(100, len(self.df)):
            df_simdi = self.df.iloc[:i].copy()
            bulunanlar = dedektor.analiz_et(df_simdi, self.sembol, self.zaman_dilimi.upper())
            
            for s in bulunanlar:
                s.olustugu_index = i - 1
                s.olustugu_fiyat = df_simdi['close'].iloc[-1]
                sinyaller.append(s)
                
        logger.info(f"   {tip}: {len(sinyaller)} sinyal")
        return sinyaller

    def _simule_et(self, sinyal, index):
        """Sinyali simüle et (24 saat sonraki fiyat)"""
        baslangic_fiyat = sinyal.olustugu_fiyat
        
        # 24 saat sonraki fiyat
        if index + 24 >= len(self.df):
            return 'yetersiz_veri'
            
        sonraki_fiyat = self.df['close'].iloc[index + 24]
        
        if sinyal.yon == 'BULLISH':
            return 'basarili' if sonraki_fiyat > baslangic_fiyat else 'basarisiz'
        else:
            return 'basarili' if sonraki_fiyat < baslangic_fiyat else 'basarisiz'

    async def calistir(self):
        """Backtest'i çalıştır"""
        print("\n" + "="*60)
        print(f"🔬 BACKTEST BAŞLATILIYOR")
        print(f"Sembol: {self.sembol}")
        print(f"Periyot: Son {self.gun} gün")
        print(f"Zaman Dilimi: {self.zaman_dilimi}")
        print("="*60)
        
        if not await self.veri_cek():
            return

        # Sinyalleri bul
        msb_sinyaller = self._sinyal_bul(msb_detector, 'MSB')
        fvg_sinyaller = self._sinyal_bul(fvg_detector, 'FVG')
        crt_sinyaller = self._sinyal_bul(crt_detector, 'CRT')
        
        self.tum_sinyaller = msb_sinyaller + fvg_sinyaller + crt_sinyaller

        # Simüle et
        logger.info("⚙️ Sinyaller simüle ediliyor...")
        
        for sinyal in self.tum_sinyaller:
            tip = type(sinyal).__name__.replace('Sinyali', '')
            sonuc = self._simule_et(sinyal, sinyal.olustugu_index)
            
            if sonuc == 'basarili':
                self.sonuclar[tip]['basarili'] += 1
            elif sonuc == 'basarisiz':
                self.sonuclar[tip]['basarisiz'] += 1
            
            self.sonuclar[tip]['toplam'] += 1

        # Rapor göster
        self.rapor_goster()

    def rapor_goster(self):
        """Sonuçları tablo halinde göster"""
        print("\n" + "="*60)
        print("📊 BACKTEST RAPORU")
        print("="*60)
        
        tablo = []
        for tip, veri in self.sonuclar.items():
            if veri['toplam'] > 0:
                basari_yuzde = (veri['basarili'] / veri['toplam']) * 100
                tablo.append([
                    tip,
                    veri['toplam'],
                    veri['basarili'],
                    veri['basarisiz'],
                    f"%{basari_yuzde:.1f}"
                ])
            else:
                tablo.append([tip, 0, 0, 0, "%0"])
        
        print(tabulate(tablo, 
                      headers=['Sinyal', 'Toplam', '✅ Başarılı', '❌ Başarısız', 'Başarı Oranı'],
                      tablefmt='grid'))
        print("="*60)

async def main():
    """Ana test fonksiyonu"""
    print("🎯 BACKTEST SİSTEMİ")
    
    # BTC testi
    bt = Backtest(sembol='BTC/USDT', gun=30, zaman_dilimi='1h')
    await bt.calistir()
    
    # Bağlantıları kapat
    await veri_topla.kapat()

if __name__ == "__main__":
    asyncio.run(main())