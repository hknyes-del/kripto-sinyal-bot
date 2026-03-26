"""
╔══════════════════════════════════════════════════════════════╗
║  DOSYA 8: handlers/start_handler.py — Başlangıç & Ana Menü  ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya:  /start komutu, karşılama mesajı, ana menü
navigasyonu ve piyasa özeti görüntüleme işlemlerini yönetir.
"""

import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from config import TIMEZONE, INITIAL_BALANCE, EMOJI as E
from database import get_or_create_user, get_user
from keyboards import main_menu_keyboard, back_to_main
from utils.market_data import get_market_overview, get_fear_greed_index, get_24h_ticker

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


async def _run_sync(func, *args):
    """Blocking fonksiyonu async'e çevirir."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)



# ═══════════════════════════════════════════════
#  /start KOMUTU
# ═══════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcıyı karşılar ve ana menüyü gösterir."""
    logger.info(f"📥 /start komutu alındı: {update.effective_user.id} ({update.effective_user.username})")
    try:
        user_tg = update.effective_user
        user    = get_or_create_user(
            user_id    = user_tg.id,
            username   = user_tg.username,
            first_name = user_tg.first_name,
        )
        logger.debug(f"👤 Kullanıcı kaydı kontrol edildi/oluşturuldu: {user_tg.id}")

    except Exception as e:
        logger.error(f"❌ /start komutu işlenirken hata: {e}")
        await update.message.reply_text("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")
        return

    now_tr = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")
    name   = user_tg.first_name or "Trader"

    welcome = (
        f"╔══════════════════════════════╗\n"
        f"║  {E['lightning']} KRİPTO SİNYAL BOTU {E['lightning']}  ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"Merhaba, **{name}**! {E['star']}\n\n"
        f"🕐 {now_tr} (GMT+3)\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{E['dollar']} **DEMO HESABINIZ:**\n"
        f"   Bakiye: **${user['balance']:,.2f}**\n"
        f"   Toplam P&L: **${user['total_pnl']:+.2f}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Aşağıdan bir bölüm seçin:\n"
    )

    logger.debug(f"📤 Menü gönderiliyor: {user_tg.id}")
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    logger.info(f"✅ /start başarıyla tamamlandı: {user_tg.id}")


# ═══════════════════════════════════════════════
#  ANA MENÜ CALLBACK
# ═══════════════════════════════════════════════

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menüyü gösterir (callback ile)."""
    query   = update.callback_query
    await query.answer()

    user    = get_user(query.from_user.id)
    now_tr  = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")

    balance  = user["balance"] if user else INITIAL_BALANCE
    total_pnl = user["total_pnl"] if user else 0.0
    pnl_emoji = E["profit"] if total_pnl >= 0 else E["loss"]

    text = (
        f"🏠 **ANA MENÜ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_tr} (GMT+3)\n\n"
        f"{E['dollar']} **HESAP DURUMU:**\n"
        f"   Bakiye:    **${balance:,.2f}**\n"
        f"   Toplam P&L: {pnl_emoji} **${total_pnl:+.2f}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Bir bölüm seçin:"
    )

    await _safe_edit(query, 
        text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ═══════════════════════════════════════════════
#  PİYASA ÖZETİ
# ═══════════════════════════════════════════════

async def market_overview_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Piyasa özeti sayfası."""
    query = update.callback_query
    await query.answer("Piyasa verileri yükleniyor...")

    fng     = await _run_sync(get_fear_greed_index)
    market  = await _run_sync(get_market_overview)

    text = (
        f"📉 **PİYASA ÖZETİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M')} GMT+3\n\n"

        f"{fng['emoji']} **Korku & Açgözlülük Endeksi:**\n"
        f"   {fng['value']}/100 — {fng['label']}\n\n"

        f"💹 **COIN FİYATLARI:**\n"
    )

    for m in market:
        arrow = "📈" if m["change"] >= 0 else "📉"
        sign  = "+" if m["change"] >= 0 else ""
        text += (
            f"  {arrow} **{m['pair']}**\n"
            f"     ${m['price']:,.2f} | {sign}{m['change']:.2f}%\n"
            f"     Hacim: ${m['volume']:,.0f}\n"
        )

    text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n⚡ Binance verisi"

    from keyboards import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Yenile", callback_data="menu_market"),
         InlineKeyboardButton("◀️ Ana Menü", callback_data="menu_main")],
    ])

    await _safe_edit(query, text, parse_mode="Markdown", reply_markup=kb)


# ═══════════════════════════════════════════════
#  /YARDIM KOMUTU
# ═══════════════════════════════════════════════

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım mesajı."""
    text = (
        f"{E['info']} **BOT KOMUTLARI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"/start — Ana menüyü aç\n"
        f"/sinyal — Sinyal tara\n"
        f"/pozisyon — Aktif pozisyonlar\n"
        f"/pnl — Kar/Zarar raporu\n"
        f"/market — Piyasa özeti\n"
        f"/ayarlar — Ayarlar\n"
        f"/yardim — Bu mesaj\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Bu bot finansal tavsiye vermez.\n"
        f"Tüm işlemler demo hesap üzerindedir."
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=back_to_main()
    )


# ═══════════════════════════════════════════════
#  HANDLER KAYITLARI
# ═══════════════════════════════════════════════

def register_start_handlers(app):
    """Tüm start handler'larını uygulamaya kaydeder."""
    app.add_handler(CommandHandler("start",   start_command))
    app.add_handler(CommandHandler("yardim",  help_command))
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CallbackQueryHandler(main_menu_callback,     pattern="^menu_main$"))
    app.add_handler(CallbackQueryHandler(market_overview_callback, pattern="^menu_market$"))
    logger.info("✅ Start handlers kayıtlandı.")
