import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from veri.veri_topla import veri_topla
from sinyaller.crt_detector import crt_detector
from sinyaller.msb_detector import msb_detector
from sinyaller.fvg_retrace import fvg_detector
from config import config

async def test_msb_fvg_entegrasyonu():
    """MSB + FVG entegrasyon testi"""
    print("\n" + "🔥"*60)
    print("🔥 MSB + FVG ENTEGRASYON TESTİ")
    print("🔥"*60)
    
    from main import KriptoSinyalSistemi
    sistem = KriptoSinyalSistemi()
    
    # Verileri yükle
    print("\n📥 Veriler yükleniyor...")
    await veri_topla.tum_verileri_guncelle(['BTC/USDT', 'ETH/USDT'], limit=200)
    
    # MSB tara
    print("\n🔍 MSB taranıyor...")
    msb_sinyalleri = await sistem.msb_tarama_yap()
    print(f"   MSB Sinyalleri: {len(msb_sinyalleri)}")
    
    # FVG tara
    print("\n🔍 FVG taranıyor...")
    fvg_sinyalleri = await sistem.fvg_tarama_yap()
    print(f"   FVG Sinyalleri: {len(fvg_sinyalleri)}")
    
    # MSB+FVG entegrasyonu
    print("\n🎯 MSB+FVG entegrasyonu hesaplanıyor...")
    entegrasyon = await sistem.msb_fvg_entegrasyonu(msb_sinyalleri, fvg_sinyalleri)
    
    print(f"\n🔥 ENTEGRASYON SİNYALLERİ: {len(entegrasyon)}")
    
    for i, sinyal in enumerate(entegrasyon[:5], 1):
        print(f"\n   {i}. 🔥 MSB+FVG SİNYALİ")
        print(f"      Sembol: {sinyal['sembol']}")
        print(f"      Zaman: {sinyal['zaman_dilimi']}")
        print(f"      Yön: {sinyal['yon']}")
        print(f"      MSB: {sinyal['msb_tip']} @ ${sinyal['msb_fiyat']:.2f}")
        print(f"      FVG Derinlik: %{sinyal['fvg_derinlik']:.1f}")
        print(f"      Order Block: {sinyal['order_block']}")
        print(f"      Güven: %{sinyal['guven_skoru']:.0f}")
        print(f"      Entry: ${sinyal['entry_fiyat']:.2f}")
        print(f"      SL: ${sinyal['stop_loss']:.2f}")
        print(f"      TP: ${sinyal['take_profit'][2]:.2f}")
    
    await veri_topla.kapat()
    return entegrasyon

async def main():
    print("🚀 MSB+FVG ENTEGRASYON TESTİ BAŞLATILIYOR...")
    print(f"⏰ Test zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        entegrasyon = await test_msb_fvg_entegrasyonu()
        
        print("\n" + "="*60)
        print("📊 TEST ÖZETİ")
        print("="*60)
        print(f"✅ MSB+FVG Entegrasyon Sinyali: {len(entegrasyon)}")
        print(f"✅ Yüksek Güvenli (80+): {len([s for s in entegrasyon if s['guven_skoru'] >= 80])}")
        print("\n🎉 TEST TAMAMLANDI!")
        
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        await veri_topla.kapat()

if __name__ == "__main__":
    asyncio.run(main())