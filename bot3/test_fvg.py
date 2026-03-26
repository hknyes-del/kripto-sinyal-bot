from sinyaller.fvg_retrace import fvg_detector
from veri.veri_topla import veri_topla
import asyncio
import pandas as pd

async def test():
    df = await veri_topla.veri_cek_rest('BTC/USDT', '1h', 100)
    print(f'📊 Veri: {len(df)} mum')
    print(f'📈 Son fiyat: {df["close"].iloc[-1]:.2f}')
    
    fvg_zones = fvg_detector._fvg_tespit(df)
    print(f'\n🎯 Tespit edilen FVG: {len(fvg_zones)}')
    
    for i, fvg in enumerate(fvg_zones[:5]):
        print(f'\nFVG {i+1}:')
        print(f'   Tip: {fvg["tip"]}')
        print(f'   Bölge: {fvg["alt"]:.2f} - {fvg["ust"]:.2f}')
        print(f'   Büyüklük: %{fvg["buyukluk"]:.3f}')
        print(f'   Yaş: {fvg["yas"]} mum')
    
    await veri_topla.kapat()

asyncio.run(test())