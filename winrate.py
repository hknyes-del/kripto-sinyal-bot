import sqlite3
import json

conn = sqlite3.connect('crypto_bot.db')
trades = conn.execute('SELECT * FROM trade_history').fetchall()
cols = [d[0] for d in conn.execute('SELECT * FROM trade_history LIMIT 1').description]
conn.close()

trades = [dict(zip(cols, t)) for t in trades]

print(f"{'='*50}")
print(f"TOPLAM TRADE: {len(trades)}")
print(f"{'='*50}\n")

# Genel win rate
wins   = [t for t in trades if t['net_pnl'] and t['net_pnl'] > 0]
losses = [t for t in trades if t['net_pnl'] and t['net_pnl'] <= 0]
total_pnl = sum(t['net_pnl'] for t in trades if t['net_pnl'])

print(f"GENEL")
print(f"  Kazanan : {len(wins)} | Kaybeden: {len(losses)}")
print(f"  Win Rate: %{len(wins)/len(trades)*100:.1f}")
print(f"  Toplam P&L: ${total_pnl:.2f}")
if losses:
    avg_win  = sum(t['net_pnl'] for t in wins)  / len(wins)  if wins  else 0
    avg_loss = sum(t['net_pnl'] for t in losses) / len(losses)
    print(f"  Ort. Kazanç: ${avg_win:.2f} | Ort. Kayıp: ${avg_loss:.2f}")
print()

# Yön bazında
for direction in ['LONG', 'SHORT']:
    d_trades = [t for t in trades if t['direction'] == direction]
    if not d_trades: continue
    d_wins = [t for t in d_trades if t['net_pnl'] and t['net_pnl'] > 0]
    print(f"{direction}: {len(d_wins)}/{len(d_trades)} = %{len(d_wins)/len(d_trades)*100:.1f} | P&L: ${sum(t['net_pnl'] for t in d_trades if t['net_pnl']):.2f}")

print()

# Sinyal tipi bazında
print("SİNYAL TİPİ")
for sig in ['MSB_FVG', 'CRT', 'NORMAL']:
    s_trades = [t for t in trades if t['signal_source'] == sig]
    if not s_trades: continue
    s_wins = [t for t in s_trades if t['net_pnl'] and t['net_pnl'] > 0]
    pnl = sum(t['net_pnl'] for t in s_trades if t['net_pnl'])
    print(f"  {sig}: {len(s_wins)}/{len(s_trades)} = %{len(s_wins)/len(s_trades)*100:.1f} | P&L: ${pnl:.2f}")

print()

# TP/SL dağılımı
tp1 = sum(1 for t in trades if t['close_reason'] == 'TP1')
tp2 = sum(1 for t in trades if t['close_reason'] == 'TP2')
tp3 = sum(1 for t in trades if t['close_reason'] == 'TP3')
sl  = sum(1 for t in trades if t['close_reason'] == 'SL')
man = sum(1 for t in trades if t['close_reason'] == 'MANUAL')
print(f"TP/SL DAĞILIMI")
print(f"  TP1: {tp1} | TP2: {tp2} | TP3: {tp3} | SL: {sl} | MANUEL: {man}")

print()

# Son 10 trade
print("SON 10 TRADE")
print(f"{'Pair':<12} {'Yön':<6} {'P&L':>7} {'Sonuç'}")
print("-"*40)
for t in sorted(trades, key=lambda x: x['closed_at'] or '', reverse=True)[:10]:
    pnl = t['net_pnl'] or 0
    sonuc = t["close_reason"] or "?"
    emoji = "✅" if pnl > 0 else "❌"
    print(f"{t['pair']:<12} {t['direction']:<6} ${pnl:>6.2f} {emoji} {sonuc}")
