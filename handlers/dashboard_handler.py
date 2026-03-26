"""
handlers/dashboard_handler.py — /dashboard komutu
Performans analizi: coin, seans, sinyal tipi, yön bazında istatistikler.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import DATABASE_PATH, TIMEZONE

logger = logging.getLogger(__name__)


def _get_trades(user_id: int, days: int = 30) -> list:
    """Son N günün işlemlerini çek."""
    try:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM trade_history 
                   WHERE user_id = ? AND closed_at >= ?
                   ORDER BY closed_at DESC""",
                (user_id, since)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Dashboard veri hatası: {e}")
        return []


def _wr(trades: list) -> float:
    """Winrate hesapla."""
    if not trades:
        return 0
    wins = sum(1 for t in trades if (t.get("net_pnl") or 0) > 0)
    return wins / len(trades) * 100


def _pnl(trades: list) -> float:
    return sum(t.get("net_pnl") or 0 for t in trades)


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dashboard komutu."""
    user_id = update.effective_user.id
    trades  = _get_trades(user_id, days=30)

    if not trades:
        await update.message.reply_text("📭 Son 30 günde kapatılmış işlem yok.")
        return

    total  = len(trades)
    wins   = sum(1 for t in trades if (t.get("net_pnl") or 0) > 0)
    losses = total - wins
    wr     = wins / total * 100
    net    = _pnl(trades)

    # ── Yön bazında ─────────────────────────────────────
    long_t  = [t for t in trades if t.get("direction") == "LONG"]
    short_t = [t for t in trades if t.get("direction") == "SHORT"]

    # ── Sinyal tipi bazında ──────────────────────────────
    normal_t  = [t for t in trades if t.get("signal_source") == "NORMAL"]
    msb_t     = [t for t in trades if t.get("signal_source") == "MSB_FVG"]
    crt_t     = [t for t in trades if t.get("signal_source") == "CRT"]

    # ── En iyi / en kötü coin ────────────────────────────
    coin_stats = {}
    for t in trades:
        pair = t.get("pair", "?").replace("USDT", "")
        if pair not in coin_stats:
            coin_stats[pair] = {"pnl": 0, "count": 0, "wins": 0}
        coin_stats[pair]["pnl"]   += t.get("net_pnl") or 0
        coin_stats[pair]["count"] += 1
        if (t.get("net_pnl") or 0) > 0:
            coin_stats[pair]["wins"] += 1

    sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)
    best_coins  = sorted_coins[:3]
    worst_coins = sorted_coins[-3:]

    # ── Seans bazında ────────────────────────────────────
    seans_stats = {}
    for t in trades:
        opened = t.get("opened_at", "")
        try:
            dt   = datetime.fromisoformat(opened)
            hour = dt.hour + 3  # UTC → TR
            if hour >= 24: hour -= 24
            if 1 <= hour < 10:
                seans = "Asya"
            elif 10 <= hour < 15:
                seans = "Londra"
            elif 15 <= hour < 19:
                seans = "Overlap"
            elif 19 <= hour < 22:
                seans = "New York"
            else:
                seans = "Diğer"
        except:
            seans = "Bilinmiyor"

        if seans not in seans_stats:
            seans_stats[seans] = {"pnl": 0, "count": 0, "wins": 0}
        seans_stats[seans]["pnl"]   += t.get("net_pnl") or 0
        seans_stats[seans]["count"] += 1
        if (t.get("net_pnl") or 0) > 0:
            seans_stats[seans]["wins"] += 1

    # ── TP/SL dağılımı ───────────────────────────────────
    tp1 = sum(1 for t in trades if t.get("close_reason") == "TP1")
    tp2 = sum(1 for t in trades if t.get("close_reason") == "TP2")
    tp3 = sum(1 for t in trades if t.get("close_reason") == "TP3")
    sl  = sum(1 for t in trades if t.get("close_reason") == "SL")

    # ── Ortalama işlem süresi ────────────────────────────
    durations = [t.get("duration_mins") or 0 for t in trades if t.get("duration_mins")]
    avg_dur   = int(sum(durations) / len(durations)) if durations else 0
    if avg_dur >= 60:
        dur_str = f"{avg_dur // 60}s {avg_dur % 60}dk"
    else:
        dur_str = f"{avg_dur}dk"

    # ── Mesajı oluştur ───────────────────────────────────
    def wr_line(t_list, label):
        if not t_list: return f"  {label}: veri yok"
        w = sum(1 for t in t_list if (t.get("net_pnl") or 0) > 0)
        p = _pnl(t_list)
        sign = "+" if p >= 0 else ""
        return f"  {label}: {w}/{len(t_list)} = %{w/len(t_list)*100:.0f} | {sign}${p:.2f}"

    # Coin satırları
    best_str = ""
    for coin, s in best_coins:
        if s["count"] == 0: continue
        sign = "+" if s["pnl"] >= 0 else ""
        best_str += f"  ✅ {coin}: {s['wins']}/{s['count']} | {sign}${s['pnl']:.2f}\n"

    worst_str = ""
    for coin, s in worst_coins:
        if s["count"] == 0: continue
        sign = "+" if s["pnl"] >= 0 else ""
        worst_str += f"  ❌ {coin}: {s['wins']}/{s['count']} | {sign}${s['pnl']:.2f}\n"

    # Seans satırları
    seans_str = ""
    for seans in ["Overlap", "Londra", "New York", "Asya"]:
        if seans not in seans_stats: continue
        s = seans_stats[seans]
        if s["count"] == 0: continue
        seans_wr = s["wins"] / s["count"] * 100
        sign = "+" if s["pnl"] >= 0 else ""
        em = "⚡" if seans == "Overlap" else "🇬🇧" if seans == "Londra" else "🗽" if seans == "New York" else "🌙"
        seans_str += f"  {em} {seans}: %{seans_wr:.0f} | {sign}${s['pnl']:.2f} ({s['count']} işlem)\n"

    net_sign = "+" if net >= 0 else ""
    now_str  = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")

    msg = (
        f"📊 **PERFORMANS DASHBOARD**\n"
        f"{'─'*32}\n"
        f"🕐 {now_str} | Son 30 gün\n\n"

        f"**GENEL**\n"
        f"  İşlem: {total} | Kazanan: {wins} | Kaybeden: {losses}\n"
        f"  Winrate: **%{wr:.1f}**\n"
        f"  Net P&L: **{net_sign}${net:.2f}**\n"
        f"  Ort. süre: {dur_str}\n\n"

        f"**YÖN**\n"
        f"{wr_line(long_t, '📈 LONG')}\n"
        f"{wr_line(short_t, '📉 SHORT')}\n\n"

        f"**SİNYAL TİPİ**\n"
        f"{wr_line(normal_t, '🚀 NORMAL')}\n"
        f"{wr_line(msb_t,    '🎯 MSB_FVG')}\n"
        f"{wr_line(crt_t,    '🏆 CRT')}\n\n"

        f"**TP/SL DAĞILIMI**\n"
        f"  TP1:{tp1} | TP2:{tp2} | TP3:{tp3} | SL:{sl}\n\n"

        f"**EN İYİ COİNLER**\n"
        f"{best_str}\n"
        f"**EN KÖTÜ COİNLER**\n"
        f"{worst_str}\n"
        f"**SEANS PERFORMANSI**\n"
        f"{seans_str}"
    )

    # Markdown özel karakterleri temizle
    safe_msg = msg.replace("*", "").replace("`", "").replace("_", "")
    await update.message.reply_text(safe_msg[:4096])


def register_dashboard_handlers(app):
    """Dashboard handler'ını kaydeder."""
    app.add_handler(CommandHandler("dashboard", dashboard_command))
    logger.info("✅ Dashboard handler kayıtlandı.")
