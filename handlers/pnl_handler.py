"""
╔══════════════════════════════════════════════════════════════╗
║   DOSYA 11: handlers/pnl_handler.py — Kar/Zarar Analitik    ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Tüm kapatılmış işlemlerin kapsamlı performans
analizi, istatistikler, işlem geçmişi ve raporlama
işlemlerini yönetir. Farklı zaman dilimleri ve filtreler.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from config import TIMEZONE, EMOJI as E, INITIAL_BALANCE
from database import get_user, get_trade_history, get_user_stats
from keyboards import pnl_menu_keyboard, back_to_main, back_button
from utils.calculations import calculate_pnl_statistics

logger = logging.getLogger(__name__)

async def _safe_edit(query, text, parse_mode="Markdown", reply_markup=None):
    """Mesajı güvenli günceller — photo mesajı olsa bile çalışır."""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        try:
            await query.edit_message_caption(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            try:
                await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            except Exception:
                pass



# ═══════════════════════════════════════════════
#  P&L ANA MENÜSÜ
# ═══════════════════════════════════════════════

async def pnl_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kar/Zarar ana menüsü — Genel özet."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user    = get_user(user_id)
    stats   = get_user_stats(user_id, days=30)

    balance     = user["balance"] if user else INITIAL_BALANCE
    init_bal    = user.get("initial_balance", INITIAL_BALANCE) if user else INITIAL_BALANCE
    total_pnl   = user["total_pnl"] if user else 0
    total_return = ((balance - init_bal) / init_bal * 100) if init_bal > 0 else 0

    pnl_em  = "💰" if total_pnl >= 0 else "🔴"
    ret_em  = "📈" if total_return >= 0 else "📉"

    # 30 günlük stats
    win_rate = stats.get("win_rate", 0)
    total_tr = stats.get("total_trades") or 0
    pf       = round(stats.get("gross_profit", 0) / stats.get("gross_loss", 1), 2) \
               if stats.get("gross_loss") else "∞"

    text = (
        f"📊 **KAR / ZARAR ANALİTİĞİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🕐 {datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M')} GMT+3\n\n"

        f"💵 **HESAP DURUMU:**\n"
        f"  Başlangıç: **${init_bal:,.2f}**\n"
        f"  Güncel:    **${balance:,.2f}**\n"
        f"  {pnl_em} Toplam P&L: **${total_pnl:+.2f}**\n"
        f"  {ret_em} Toplam Getiri: **%{total_return:+.2f}**\n\n"

        f"📈 **SON 30 GÜN:**\n"
        f"  İşlem Sayısı: **{total_tr}**\n"
        f"  Kazanma Oranı: **%{win_rate:.1f}**\n"
        f"  Kazanan/Kaybeden: **{stats.get('winning_trades',0)}/{stats.get('losing_trades',0)}**\n"
        f"  Profit Factor: **{pf}**\n"
        f"  Ort. Kazanç: **${stats.get('avg_win', 0):+.2f}**\n"
        f"  Ort. Kayıp: **${stats.get('avg_loss', 0):.2f}**\n\n"

        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Zaman dilimi seçin:"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=pnl_menu_keyboard()
    )


# ═══════════════════════════════════════════════
#  DÖNEM BAZLI RAPOR
# ═══════════════════════════════════════════════

async def pnl_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Belirli dönem için P&L raporu."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    days    = int(query.data.replace("pnl_period_", ""))

    period_labels = {
        1: "Bugün", 7: "Bu Hafta", 30: "Bu Ay",
        90: "Son 3 Ay", 365: "Son 1 Yıl", 0: "Tüm Zamanlar"
    }
    label  = period_labels.get(days, f"Son {days} Gün")
    query_days = 36500 if days == 0 else days

    trades = get_trade_history(user_id, limit=500)

    # Dönem filtresi
    if days > 0:
        cutoff = datetime.utcnow()
        from datetime import timedelta
        cutoff_dt = cutoff - timedelta(days=days)
        filtered_trades = []
        for t in trades:
            try:
                t_date = datetime.fromisoformat(t.get("closed_at", "1970-01-01"))
                if t_date >= cutoff_dt:
                    filtered_trades.append(t)
            except:
                pass
        trades = filtered_trades

    if not trades:
        await _safe_edit(query, 
            f"📊 **{label} P&L Raporu**\n\n"
            f"📭 Bu dönemde kapatılmış işlem bulunmuyor.",
            reply_markup=pnl_menu_keyboard()
        )
        return

    stats = calculate_pnl_statistics(trades)

    pnl_em  = "💰" if stats["total_pnl"] >= 0 else "🔴"
    wr_em   = "🏆" if stats["win_rate"] >= 70 else "📊" if stats["win_rate"] >= 50 else "⚠️"

    text = (
        f"📊 **{label.upper()} P&L RAPORU**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📈 **GENEL BAKIŞ:**\n"
        f"  Toplam İşlem: **{stats['total_trades']}**\n"
        f"  {wr_em} Kazanma Oranı: **%{stats['win_rate']:.1f}**\n"
        f"  Kazanan: {stats['win_count']} | Kaybeden: {stats['loss_count']}\n\n"

        f"💰 **FİNANSAL:**\n"
        f"  {pnl_em} Toplam P&L: **${stats['total_pnl']:+.2f}**\n"
        f"  Brüt Kâr: **+${stats['gross_profit']:,.2f}**\n"
        f"  Brüt Zarar: **-${stats['gross_loss']:,.2f}**\n"
        f"  Profit Factor: **{stats['profit_factor']}**\n\n"

        f"📐 **ORTALAMALAR:**\n"
        f"  Ort. Kazanç: **+${stats['avg_win']:,.2f}**\n"
        f"  Ort. Kayıp:  **-${stats['avg_loss']:,.2f}**\n"
        f"  Ort. P&L:     **${stats['avg_pnl']:+.2f}**\n\n"

        f"🏆 **EN İYİ / EN KÖTÜ:**\n"
        f"  🥇 En iyi işlem:  **+${stats['best_trade']:,.2f}**\n"
        f"  💀 En kötü işlem: **${stats['worst_trade']:,.2f}**\n\n"

        f"📉 **RİSK METRİKLERİ:**\n"
        f"  Max Drawdown: **${stats['max_drawdown']:,.2f}**\n"
        f"  Sharpe Oranı: **{stats['sharpe_ratio']}**\n"
        f"  Maks. Kazanma Serisi: **{stats['max_win_streak']} işlem**\n"
        f"  Maks. Kaybetme Serisi: **{stats['max_lose_streak']} işlem**\n"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 İşlem Listesi", callback_data="pnl_history"),
             InlineKeyboardButton("🔄 Yenile",        callback_data=query.data)],
            [InlineKeyboardButton("◀️ P&L Menüsü",   callback_data="menu_pnl")],
        ])
    )


# ═══════════════════════════════════════════════
#  İŞLEM GEÇMİŞİ
# ═══════════════════════════════════════════════

async def pnl_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Son 20 işlemi gösterir."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    trades  = get_trade_history(user_id, limit=20)

    if not trades:
        await _safe_edit(query, 
            "📋 **İŞLEM GEÇMİŞİ**\n\nHenüz kapatılmış işlem yok.",
            reply_markup=back_button("menu_pnl")
        )
        return

    text = f"📋 **SON {len(trades)} İŞLEM**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for t in trades:
        d_em   = "📈" if t["direction"] == "LONG" else "📉"
        p_em   = "💚" if t["net_pnl"] > 0 else "❤️"
        sign   = "+" if t["net_pnl"] > 0 else ""
        pair   = t["pair"].replace("USDT", "/USDT")
        closed = t.get("closed_at", "")[:10] if t.get("closed_at") else ""
        reason = t.get("close_reason", "")

        reason_emoji = {
            "TP1": "🎯", "TP2": "🎯🎯", "TP3": "🏆",
            "SL": "🛑", "MANUAL": "✋", "LIQUIDATION": "💀",
        }.get(reason, "⚫")

        text += (
            f"{d_em} **{pair}** {t['leverage']}x {reason_emoji}\n"
            f"   {p_em} **{sign}${t['net_pnl']:,.2f}** ({sign}{t['roi_pct']:.1f}%)\n"
            f"   {t['entry_price']:,.4f} → {t['exit_price']:,.4f} | {closed}\n\n"
        )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ P&L Menüsü", callback_data="menu_pnl")],
        ])
    )


# ═══════════════════════════════════════════════
#  COİN BAZLI ANALİZ
# ═══════════════════════════════════════════════

async def pnl_by_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Her coin için ayrı performans analizi."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    trades  = get_trade_history(user_id, limit=500)

    if not trades:
        await _safe_edit(query, 
            "💹 **COİN BAZLI ANALİZ**\n\nHenüz veri yok.",
            reply_markup=back_button("menu_pnl")
        )
        return

    # Coin bazında grupla
    coin_data: dict = {}
    for t in trades:
        pair = t["pair"]
        if pair not in coin_data:
            coin_data[pair] = []
        coin_data[pair].append(t)

    text = "💹 **COİN BAZLI PERFORMANS**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # P&L'e göre sırala
    coin_stats = []
    for pair, tr in coin_data.items():
        s = calculate_pnl_statistics(tr)
        coin_stats.append((pair, s, len(tr)))

    coin_stats.sort(key=lambda x: x[1]["total_pnl"], reverse=True)

    for pair, s, count in coin_stats:
        p_em  = "💚" if s["total_pnl"] >= 0 else "❤️"
        sign  = "+" if s["total_pnl"] >= 0 else ""
        label = pair.replace("USDT", "/USDT")

        text += (
            f"**{label}** — {count} işlem\n"
            f"  {p_em} P&L: **{sign}${s['total_pnl']:,.2f}**\n"
            f"  Kazanma: **%{s['win_rate']:.1f}** "
            f"({s['win_count']}/{s['total_trades']})\n"
            f"  Profit Factor: **{s['profit_factor']}**\n\n"
        )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=back_button("menu_pnl", "◀️ P&L Menüsü")
    )


# ═══════════════════════════════════════════════
#  HANDLER KAYITLARI
# ═══════════════════════════════════════════════

def register_pnl_handlers(app):
    """P&L handler'larını kaydeder."""
    app.add_handler(CommandHandler("pnl",  pnl_menu_callback))
    app.add_handler(CallbackQueryHandler(pnl_menu_callback,    pattern="^menu_pnl$"))
    app.add_handler(CallbackQueryHandler(pnl_period_callback,  pattern="^pnl_period_"))
    app.add_handler(CallbackQueryHandler(pnl_history_callback, pattern="^pnl_history$"))
    app.add_handler(CallbackQueryHandler(pnl_by_coin_callback, pattern="^pnl_by_coin$"))
    logger.info("✅ PnL handlers kayıtlandı.")
