from veri.veri_topla import veri_topla
import asyncio
import pandas as pd

async def fvg_manuel_test():
    print("🔍 FVG MANUEL TEST (ETH/USDT)")
    print("="*50)
    
    # ETH 1H verisi çek
    print("📥 ETH/USDT 1H verisi çekiliyor...")
    df = await veri_topla.veri_cek_rest('ETH/USDT', '1h', 100)
    
    if df.empty:
        print("❌ Veri yok! (Binance bağlantı hatası)")
        await veri_topla.kapat()
        return
    
    print(f"✅ {len(df)} mum başarıyla çekildi!")
    print(f"📈 Son fiyat: ${df['close'].iloc[-1]:,.2f}")
    print(f"📅 Tarih aralığı: {df.index[0]} - {df.index[-1]}")
    
    # MANUEL FVG KONTROLÜ
    fvg_bulunan = 0
    fvg_detay = []
    
    print("\n🔎 FVG taranıyor...")
    
    for i in range(3, len(df)-1):
        mum1 = df.iloc[i-2]  # 2 mum önce
        mum2 = df.iloc[i-1]  # 1 mum önce
        
        # Yükseliş FVG
        if mum2['low'] > mum1['high']:
            fark = mum2['low'] - mum1['high']
            fvg_bulunan += 1
            fvg_detay.append({
                'tip': 'YÜKSELİŞ',
                'index': i,
                'tarih': df.index[i],
                'mum1_high': mum1['high'],
                'mum2_low': mum2['low'],
                'fark': fark
            })
            
        # Düşüş FVG
        if mum2['high'] < mum1['low']:
            fark = mum1['low'] - mum2['high']
            fvg_bulunan += 1
            fvg_detay.append({
                'tip': 'DÜŞÜŞ',
                'index': i,
                'tarih': df.index[i],
                'mum1_low': mum1['low'],
                'mum2_high': mum2['high'],
                'fark': fark
            })
    
    # SONUÇLAR
    print("\n" + "="*50)
    print(f"📊 TOPLAM FVG: {fvg_bulunan}")
    
    if fvg_bulunan > 0:
        print("\n📋 FVG DETAYLARI:")
        for fvg in fvg_detay[:5]:  # İlk 5 tanesini göster
            if fvg['tip'] == 'YÜKSELİŞ':
                print(f"\n  ✅ {fvg['tip']} - {fvg['tarih']}")
                print(f"     Mum1 High: ${fvg['mum1_high']:.2f}")
                print(f"     Mum2 Low:  ${fvg['mum2_low']:.2f}")
                print(f"     Fark: ${fvg['fark']:.2f}")
            else:
                print(f"\n  🔻 {fvg['tip']} - {fvg['tarih']}")
                print(f"     Mum1 Low:  ${fvg['mum1_low']:.2f}")
                print(f"     Mum2 High: ${fvg['mum2_high']:.2f}")
                print(f"     Fark: ${fvg['fark']:.2f}")
    else:
        print("\n❌ Hiç FVG bulunamadı!")
        print("   Ya gerçekten yok, ya da veri çekilemedi.")
    
    await veri_topla.kapat()

if __name__ == "__main__":
    asyncio.run(fvg_manuel_test())