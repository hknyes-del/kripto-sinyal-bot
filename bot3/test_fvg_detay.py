from sinyaller.fvg_retrace import fvg_detector
from veri.veri_topla import veri_topla
import asyncio
import pandas as pd

async def test():
    df = await veri_topla.veri_cek_rest('BTC/USDT', '1h', 100)
    print(f'📊 Veri: {len(df)} mum')
    print(f'📈 Son fiyat: {df["close"].iloc[-1]:.2f}')
    
    # 1. ADIM: FVG TESPİT FONKSİYONUNU TEK TEK ÇALIŞTIR
    print('\n🔍 FVG TESPİT DETAYLARI:')
    
    fvg_sayisi = 0
    for i in range(len(df)-3, len(df)-30, -1):
        mum1 = df.iloc[i-2]
        mum2 = df.iloc[i-1]
        mum3 = df.iloc[i]
        
        # Yükseliş FVG kontrolü
        if mum2['low'] > mum1['high']:
            print(f'\n✅ Yükseliş FVG bulundu! Index: {i}')
            print(f'   Mum1 High: {mum1["high"]:.2f}')
            print(f'   Mum2 Low: {mum2["low"]:.2f}')
            print(f'   Fark: {mum2["low"] - mum1["high"]:.2f}')
            fvg_sayisi += 1
            
        # Düşüş FVG kontrolü
        if mum2['high'] < mum1['low']:
            print(f'\n✅ Düşüş FVG bulundu! Index: {i}')
            print(f'   Mum1 Low: {mum1["low"]:.2f}')
            print(f'   Mum2 High: {mum2["high"]:.2f}')
            print(f'   Fark: {mum1["low"] - mum2["high"]:.2f}')
            fvg_sayisi += 1
    
    print(f'\n🎯 Toplam FVG: {fvg_sayisi}')
    
    # 2. ADIM: ORİJİNAL FONKSİYONU ÇALIŞTIR
    fvg_zones = fvg_detector._fvg_tespit(df)
    print(f'\n🎯 Orijinal _fvg_tespit(): {len(fvg_zones)}')
    
    await veri_topla.kapat()

asyncio.run(test())
