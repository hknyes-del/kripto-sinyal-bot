import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# YAPAY VERİ - BİLEREK FVG OLUŞTUR
tarih = [datetime.now() - timedelta(hours=x) for x in range(100, 0, -1)]
df = pd.DataFrame({
    'timestamp': tarih,
    'open': [50000 + x for x in range(100)],
    'high': [50100 + x for x in range(100)],
    'low': [49900 + x for x in range(100)],
    'close': [50050 + x for x in range(100)],
    'volume': [1000 + x for x in range(100)]
})
df.set_index('timestamp', inplace=True)

# 1. YAPAY FVG EKLE (Sonlara doğru)
idx = len(df) - 10
df.iloc[idx-2, df.columns.get_loc('high')] = 50500
df.iloc[idx-1, df.columns.get_loc('low')] = 50600  # FVG oluştu!

print("🔍 YAPAY VERİ TESTİ")
print("="*50)

# 2. FVG KONTROLÜ - DOĞRUDAN
mum1 = df.iloc[idx-2]
mum2 = df.iloc[idx-1]
print(f"\n1. Mum (i-2): High = {mum1['high']:.2f}")
print(f"2. Mum (i-1): Low  = {mum2['low']:.2f}")
print(f"FVG var mı? {mum2['low'] > mum1['high']}")
print(f"Fark: {mum2['low'] - mum1['high']:.2f}")

# 3. SİNYAL ÜRET
from sinyaller.fvg_retrace import fvg_detector
sinyaller = fvg_detector.analiz_et(df, 'TEST/USDT', '1H')
print(f"\n📊 Dedektörün bulduğu FVG: {len(sinyaller)}")

if len(sinyaller) > 0:
    print("\n✅ FVG BULUNDU!")
    for s in sinyaller:
        print(f"   Yön: {s.yon}")
        print(f"   Bölge: {s.fvg_bolgesi[0]:.2f} - {s.fvg_bolgesi[1]:.2f}")
else:
    print("\n❌ DEDEKTÖR FVG BULAMADI!")
    
    # 4. ADIM ADIM KONTROL
    print("\n🔍 ADIM ADIM KONTROL:")
    fvg_zones = fvg_detector._fvg_tespit(df)
    print(f"   _fvg_tespit(): {len(fvg_zones)}")
    
    if len(fvg_zones) > 0:
        print("   ✅ FVG tespit edildi ama retrace kontrolü geçemedi!")
        
        for fvg in fvg_zones[:2]:
            retrace = fvg_detector._fvg_retrace_kontrol(df, fvg, [])
            print(f"   Retrace kontrol: {retrace is not None}")
    else:
        print("   ❌ _fvg_tespit() çalışmıyor!")
        
        # DOĞRUDAN DÖNGÜ
        print("\n🔄 MANUEL FVG TARAMASI:")
        sayac = 0
        for i in range(len(df)-3, len(df)-50, -1):
            m1 = df.iloc[i-2]
            m2 = df.iloc[i-1]
            if m2['low'] > m1['high']:
                sayac += 1
                print(f"   ✅ Index {i}: FVG bulundu! {m1['high']:.2f} -> {m2['low']:.2f}")
        print(f"   Manuel tarama: {sayac} FVG")
        