"""
Hızlı fonksiyon testi - sentetik veriyle
"""
import pandas as pd
import numpy as np

np.random.seed(42)
n = 100
dates = pd.date_range('2024-01-01', periods=n, freq='1D')

# Düşüş trendi: 100 -> 70
trend = np.linspace(100, 70, n)
noise = np.random.randn(n) * 1.5
close = trend + noise
open_ = close + np.random.randn(n) * 0.8
high = np.maximum(close, open_) + abs(np.random.randn(n)) * 0.5
low  = np.minimum(close, open_) - abs(np.random.randn(n)) * 0.5

df = pd.DataFrame(
    {'open': open_, 'high': high, 'low': low, 'close': close, 'volume': 1000.0},
    index=dates
)

# --- Modül testleri ---
from indicators.market_structure import find_swing_points, determine_trend
from indicators.fvg import find_all_fvgs
from indicators.crt import detect_choch, detect_crt
from indicators.order_blocks import find_order_blocks
from indicators.liquidity import find_equal_highs_lows
from utils.helpers import calculate_premium_discount, is_kill_zone, calculate_rr_ratio
from backtest.tracker import BacktestTracker

errors = []

try:
    sh, sl = find_swing_points(df, lookback=3)
    print(f"[OK] Swing Points: {len(sh)} high, {len(sl)} low")
except Exception as e:
    errors.append(f"Swing Points: {e}")

try:
    trend = determine_trend(df)
    print(f"[OK] Trend: {trend}")
except Exception as e:
    errors.append(f"Trend: {e}")

try:
    fvgs = find_all_fvgs(df, 'short', lookback=50)
    print(f"[OK] FVG (short): {len(fvgs)} adet")
except Exception as e:
    errors.append(f"FVG: {e}")

try:
    choch = detect_choch(df)
    choch_type = choch['type'] if choch else 'Yok'
    print(f"[OK] ChoCH: {choch_type}")
except Exception as e:
    errors.append(f"ChoCH: {e}")

try:
    crt = detect_crt(df, direction='short')
    crt_type = crt['type'] if crt else 'Yok'
    print(f"[OK] CRT: {crt_type}")
except Exception as e:
    errors.append(f"CRT: {e}")

try:
    obs = find_order_blocks(df, 'short', lookback=50)
    print(f"[OK] Order Blocks: {len(obs)} adet")
except Exception as e:
    errors.append(f"Order Blocks: {e}")

try:
    eq_h, eq_l = find_equal_highs_lows(df, lookback=50)
    print(f"[OK] Equal H/L: {len(eq_h)} highs, {len(eq_l)} lows")
except Exception as e:
    errors.append(f"Equal H/L: {e}")

try:
    pd_info = calculate_premium_discount(df['close'].iloc[-1], df['high'].max(), df['low'].min())
    print(f"[OK] Premium/Discount: {pd_info['zone']} (guc: {pd_info['strength']})")
except Exception as e:
    errors.append(f"Premium/Discount: {e}")

try:
    rr = calculate_rr_ratio(100, 95, 110)
    print(f"[OK] R:R: 1:{rr}")
except Exception as e:
    errors.append(f"R:R: {e}")

try:
    bt = BacktestTracker(max_signals=5)
    stats = bt.get_stats()
    print(f"[OK] Backtest Tracker: {stats['total_signals']} kayitli sinyal")
except Exception as e:
    errors.append(f"Backtest: {e}")

print()
if errors:
    print("=== HATALAR ===")
    for e in errors:
        print(f"  [HATA] {e}")
else:
    print("=== TUM TESTLER GECTI ===")
