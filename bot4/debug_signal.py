"""
Sinyal debug scripti — hangi adımda coin'ler eleniyor?
"""
from data.fetcher import BinanceDataFetcher
from indicators.market_structure import find_swing_points, determine_trend, detect_msb
from indicators.crt import detect_crt
from indicators.fvg import find_fvg
from utils.helpers import calculate_premium_discount, is_monday, is_kill_zone

fetcher = BinanceDataFetcher()

TEST_COINS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]

print(f"Pazartesi mi: {is_monday()}")
print(f"Kill Zone mu: {is_kill_zone()}")
print()

for symbol in TEST_COINS:
    print(f"{'='*50}")
    print(f"  {symbol}")
    print(f"{'='*50}")

    data = fetcher.fetch_coin_data(symbol)
    if not data:
        print("  [FAIL] Veri yok")
        continue

    df_1d = data['1d']
    df_4h = data['4h']
    df_1h = data['1h']
    df_15m = data['15m']

    print(f"  Veri: 1D={len(df_1d)}, 4H={len(df_4h)}, 1H={len(df_1h)}, 15M={len(df_15m)}")

    # Swing points
    sh, sl = find_swing_points(df_1d, lookback=5)
    print(f"  1D Swing: {len(sh)} high, {len(sl)} low")

    if not sh or not sl:
        print("  [ELEME] Swing point yok!")
        continue

    # Trend
    trend = determine_trend(df_1d, lookback=5)
    print(f"  1D Trend: {trend}")

    # Premium/Discount
    current = float(df_1d['close'].iloc[-1])
    pd_info = calculate_premium_discount(current, sh[-1]['price'], sl[-1]['price'])
    print(f"  Zone: {pd_info['zone']} (güç: {pd_info['strength']:.3f})")

    # Bias kararı
    if trend == 'bearish' and pd_info['zone'] == 'PREMIUM':
        bias_dir = 'short'
        print(f"  Bias: SHORT (trend bearish + premium) ✅")
    elif trend == 'bullish' and pd_info['zone'] == 'DISCOUNT':
        bias_dir = 'long'
        print(f"  Bias: LONG (trend bullish + discount) ✅")
    else:
        bias_dir = None
        print(f"  [ELEME] Bias yok! Trend={trend}, Zone={pd_info['zone']}")
        continue

    if pd_info['strength'] < 0.2:
        print(f"  [ELEME] Bias çok zayıf! ({pd_info['strength']:.3f} < 0.2)")
        continue

    # MSB 1H
    msb = detect_msb(df_1h, bias_dir)
    if msb:
        print(f"  1H MSB: {msb['type']} @ {msb['broken_level']:.4f} ✅")
    else:
        sh1h, sl1h = find_swing_points(df_1h, lookback=3)
        print(f"  [ELEME] 1H MSB yok! (1H Swing: {len(sh1h)}H, {len(sl1h)}L)")
        continue

    # FVG 15M
    fvg = find_fvg(df_15m, bias_dir)
    print(f"  15M FVG: {'VAR' if fvg else 'YOK'}")

    # CRT 4H
    crt = detect_crt(df_4h, bias_dir)
    print(f"  4H CRT: {'VAR - ' + crt['type'] if crt else 'YOK'}")

    print(f"  >>> SINYAL UÜRETİLEBİLİR ✅")

print("\nDebug tamamlandi.")
