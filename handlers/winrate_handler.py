"""
handlers/winrate_handler.py — /winrate komutu
Sinyal tipi, yön ve TP/SL dağılımı bazında winrate raporu.
"""

import logging
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


async def winrate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/winrate komutu — detaylı winrate raporu gönderir."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM trade_history").fetchall()
        conn.close()

        trades = [dict(r) for r in rows]

        if not trades:
            await update.message.reply_text("📭 Henüz kapatılmış işlem yok.")
            return

        # ── Genel ──────────────────────────────────────────
        wins   = [t for t in trades if t.get("net_pnl") and t["net_pnl"] > 0]
        losses = [t for t in trades if t.get("net_pnl") and t["net_pnl"] <= 0]
        total  = len(trades)
        total_pnl = sum(t["net_pnl"] for t in trades if t.get("net_pnl"))

        win_rate = len(wins) / total * 100 if total else 0
        avg_win  = sum(t["net_pnl"] for t in wins)   / len(wins)   if wins   else 0
        avg_loss = sum(t["net_pnl"] for t in losses) / len(losses) if losses else 0
        profit_factor = abs(sum(t["net_pnl"] for t in wins) / sum(t["net_pnl"] for t in losses)) if losses and sum(t["net_pnl"] for t in losses) != 0 else 0

        # ── Yön bazında ────────────────────────────────────
        yön_satırları = ""
        for direction in ["LONG", "SHORT"]:
            d = [t for t in trades if t.get("direction") == direction]
            if not d:
                continue
            d_wins = [t for t in d if t.get("net_pnl") and t["net_pnl"] > 0]
            d_pnl  = sum(t["net_pnl"] for t in d if t.get("net_pnl"))
            d_wr   = len(d_wins) / len(d) * 100
            em     = "📈" if direction == "LONG" else "📉"
            yön_satırları += f"  {em} {direction}: {len(d_wins)}/{len(d)} = %{d_wr:.1f} | P&L: ${d_pnl:.2f}\n"

        # ── Sinyal tipi bazında ────────────────────────────
        sinyal_satırları = ""
        for sig in ["MSB_FVG", "CRT", "NORMAL"]:
            s = [t for t in trades if t.get("signal_source") == sig]
            if not s:
                continue
            s_wins = [t for t in s if t.get("net_pnl") and t["net_pnl"] > 0]
            s_pnl  = sum(t["net_pnl"] for t in s if t.get("net_pnl"))
            s_wr   = len(s_wins) / len(s) * 100
            sinyal_satırları += f"  • {sig}: {len(s_wins)}/{len(s)} = %{s_wr:.1f} | P&L: ${s_pnl:.2f}\n"

        if not sinyal_satırları:
            sinyal_satırları = "  Veri yok\n"

        # ── TP/SL dağılımı ─────────────────────────────────
        tp1 = sum(1 for t in trades if t.get("close_reason") == "TP1")
        tp2 = sum(1 for t in trades if t.get("close_reason") == "TP2")
        tp3 = sum(1 for t in trades if t.get("close_reason") == "TP3")
        sl  = sum(1 for t in trades if t.get("close_reason") == "SL")
        man = sum(1 for t in trades if t.get("close_reason") == "MANUAL")

        # ── Son 10 işlem ───────────────────────────────────
        son_10 = sorted(trades, key=lambda x: x.get("closed_at") or "", reverse=True)[:10]
        son_satırlar = ""
        for t in son_10:
            pnl   = t.get("net_pnl") or 0
            em    = "✅" if pnl > 0 else "❌"
            pair  = (t.get("pair") or "?").replace("USDT", "/USDT")
            yön   = t.get("direction") or "?"
            sonuc = t.get("close_reason") or "?"
            son_satırlar += f"  {em} {pair} {yön} ${pnl:+.2f} ({sonuc})\n"

        # ── Mesajı oluştur ──────────────────────────────────
        msg = (
            f"📊 **WINRATE RAPORU**\n"
            f"{'─'*32}\n\n"
            f"**GENEL**\n"
            f"  Toplam: {total} | Kazanan: {len(wins)} | Kaybeden: {len(losses)}\n"
            f"  Winrate: **%{win_rate:.1f}**\n"
            f"  Toplam P&L: **${total_pnl:.2f}**\n"
            f"  Profit Factor: **{profit_factor:.2f}**\n"
            f"  Ort. Kazanç: ${avg_win:.2f} | Ort. Kayıp: ${avg_loss:.2f}\n\n"
            f"**YÖN BAZINDA**\n"
            f"{yön_satırları}\n"
            f"**SİNYAL TİPİ**\n"
            f"{sinyal_satırları}\n"
            f"**TP/SL DAĞILIMI**\n"
            f"  TP1: {tp1} | TP2: {tp2} | TP3: {tp3} | SL: {sl} | Manuel: {man}\n\n"
            f"**SON 10 İŞLEM**\n"
            f"{son_satırlar}"
        )

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Winrate hatası: {e}")
        await update.message.reply_text(f"⚠️ Hata: {e}")


def register_winrate_handlers(app):
    """Winrate handler'ını kaydeder."""
    app.add_handler(CommandHandler("winrate", winrate_command))
    logger.info("✅ Winrate handler kayıtlandı.")
