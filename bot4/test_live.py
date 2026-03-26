"""
Canlı Binance veri testi — API key gereksiz (public endpoint)
"""
from data.fetcher import BinanceDataFetcher

fetcher = BinanceDataFetcher()

coins = fetcher.fetch_top_coins(5)
print(f"Ilk 5 coin: {coins}")

print("\nBTC/USDT 1D veri cekiliyor...")
df = fetcher.fetch_ohlcv("BTC/USDT", "1d", limit=10)
if df is not None:
    print(f"  -> {len(df)} mum alindi")
    print(f"  Son kapanış: {df['close'].iloc[-1]:.2f} USDT")
else:
    print("  -> BASARISIZ!")

print("\nETH/USDT 1H veri cekiliyor...")
df2 = fetcher.fetch_ohlcv("ETH/USDT", "1h", limit=10)
if df2 is not None:
    print(f"  -> {len(df2)} mum alindi")
    print(f"  Son kapanış: {df2['close'].iloc[-1]:.2f} USDT")
else:
    print("  -> BASARISIZ!")

print("\nPOL/USDT 4H veri cekiliyor...")
df3 = fetcher.fetch_ohlcv("POL/USDT", "4h", limit=10)
if df3 is not None:
    print(f"  -> {len(df3)} mum alindi")
else:
    print("  -> POL bulunamadi (normal olabilir)")
