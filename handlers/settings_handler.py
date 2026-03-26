"""
╔══════════════════════════════════════════════════════════════╗
║  DOSYA 12: handlers/settings_handler.py — Ayarlar Yönetimi  ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Kullanıcı tercihlerini, bildirim ayarlarını,
risk parametrelerini ve veri sıfırlama işlemlerini yönetir.
Sıfırlama için çok katmanlı onay sistemi uygulanmıştır.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import TIMEZONE, INITIAL_BALANCE, EMOJI as E, LEVERAGE_OPTIONS
from database import get_user, get_user_settings, update_user_settings, reset_user_data, update_user_balance
from keyboards import (settings_menu_keyboard, confirm_reset_keyboard,
                       risk_level_keyboard, leverage_keyboard, back_button)

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
#  AYARLAR ANA MENÜSÜ
# ═══════════════════════════════════════════════

async def settings_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ayarlar ana menüsü."""
    query   = update.callback_query
    await query.answer()

    user_id  = query.from_user.id
    user     = get_user(user_id)
    settings = get_user_settings(user_id)

    notif_em = "🔔 Açık" if settings.get("notifications", 1) else "🔕 Kapalı"
    risk      = user.get("risk_level", "MEDIUM") if user else "MEDIUM"
    risk_labels = {"LOW": "🟢 Muhafazakâr", "MEDIUM": "🟡 Dengeli", "HIGH": "🔴 Agresif"}

    text = (
        f"⚙️ **AYARLAR**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **HESAP:**\n"
        f"  Bakiye: **${user['balance']:,.2f}**\n"
        f"  Risk Profili: **{risk_labels.get(risk, risk)}**\n\n"
        f"⚙️ **TERCİHLER:**\n"
        f"  Bildirimler: **{notif_em}**\n"
        f"  Varsayılan Marjin: **${user.get('default_margin', 20):.0f}**\n"
        f"  Varsayılan Kaldıraç: **{user.get('default_leverage', 5)}x**\n"
        f"  Min. Güven Skoru: **%{settings.get('min_confidence', 85)}**\n"
        f"  Oto. TP Kapat: **{'Açık ✅' if settings.get('auto_tp_close') else 'Kapalı ❌'}**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Düzenlemek istediğiniz ayarı seçin:"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=settings_menu_keyboard()
    )


# ═══════════════════════════════════════════════
#  BİLDİRİM AYARLARI
# ═══════════════════════════════════════════════

async def settings_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bildirim ayarları."""
    query   = update.callback_query
    await query.answer()

    user_id  = query.from_user.id
    settings = get_user_settings(user_id)
    current  = settings.get("notifications", 1)

    text = (
        f"🔔 **BİLDİRİM AYARLARI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Mevcut durum: **{'🔔 Açık' if current else '🔕 Kapalı'}**\n\n"
        f"Bildirim türleri:\n"
        f"  • Yeni sinyal oluştuğunda\n"
        f"  • TP seviyelerine ulaşıldığında\n"
        f"  • Stop Loss tetiklendiğinde\n"
        f"  • Margin Call uyarısı\n"
        f"  • Günlük performans özeti\n"
    )

    new_val = 0 if current else 1
    btn_label = "🔕 Bildirimleri Kapat" if current else "🔔 Bildirimleri Aç"

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_label, callback_data=f"notif_toggle_{new_val}")],
            [InlineKeyboardButton("◀️ Ayarlar", callback_data="menu_settings")],
        ])
    )


async def notif_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bildirimleri açar/kapatır."""
    query   = update.callback_query
    await query.answer()

    new_val = int(query.data.replace("notif_toggle_", ""))
    update_user_settings(query.from_user.id, notifications=new_val)

    status = "🔔 Açık" if new_val else "🔕 Kapalı"
    await query.answer(f"Bildirimler {status}", show_alert=True)
    await settings_menu_callback(update, context)


# ═══════════════════════════════════════════════
#  KALDIRAÇ AYARI
# ═══════════════════════════════════════════════

async def settings_leverage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Varsayılan kaldıraç ayarı."""
    query = update.callback_query
    await query.answer()

    await _safe_edit(query, 
        "⚡ **VARSAYILAN KALDIRAÇ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Bu değer yeni pozisyon açarken varsayılan olarak seçilir.\n"
        "Her pozisyon için ayrıca değiştirebilirsiniz.\n\n"
        "Kaldıraç seçin:",
        parse_mode="Markdown",
        reply_markup=leverage_keyboard("settings_lev")
    )


async def settings_leverage_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Varsayılan kaldıracı günceller."""
    query   = update.callback_query
    leverage = int(query.data.replace("settings_lev_", ""))
    from database import get_db
    from config import DATABASE_PATH
    import sqlite3
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "UPDATE users SET default_leverage = ? WHERE id = ?",
            (leverage, query.from_user.id)
        )
    await query.answer(f"✅ Varsayılan kaldıraç {leverage}x olarak güncellendi.", show_alert=True)
    await settings_menu_callback(update, context)


# ═══════════════════════════════════════════════
#  OTO TP KAPAT AYARI
# ═══════════════════════════════════════════════

async def settings_auto_tp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Otomatik TP kapatma ayarı."""
    query    = update.callback_query
    await query.answer()

    user_id  = query.from_user.id
    settings = get_user_settings(user_id)
    current  = settings.get("auto_tp_close", 0)

    text = (
        f"🎯 **OTOMATİK TP KAPAMA**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Mevcut durum: **{'✅ Açık' if current else '❌ Kapalı'}**\n\n"
        f"Bu özellik açıkken:\n"
        f"  • TP1'e ulaşıldığında %30'u otomatik kapatır\n"
        f"  • TP2'de %40'ı kapatır\n"
        f"  • TP3'te kalan %30'u kapatır\n\n"
        f"Kapalıyken: Her TP'de onay istenir."
    )

    new_val   = 0 if current else 1
    btn_label = "❌ Kapat" if current else "✅ Aç"

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(btn_label, callback_data=f"auto_tp_{new_val}")],
            [InlineKeyboardButton("◀️ Ayarlar", callback_data="menu_settings")],
        ])
    )


async def auto_tp_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oto TP'yi günceller."""
    query   = update.callback_query
    new_val = int(query.data.replace("auto_tp_", ""))
    update_user_settings(query.from_user.id, auto_tp_close=new_val)
    await query.answer(
        f"Otomatik TP {'Açıldı ✅' if new_val else 'Kapatıldı ❌'}",
        show_alert=True
    )
    await settings_menu_callback(update, context)


# ═══════════════════════════════════════════════
#  RİSK PROFİLİ
# ═══════════════════════════════════════════════

async def settings_risk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risk profili seçimi."""
    query = update.callback_query
    await query.answer()

    await _safe_edit(query, 
        "⚖️ **RİSK PROFİLİ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🟢 **Muhafazakâr (LOW):**\n"
        "   Max %1 risk, 3x kaldıraç, az işlem\n\n"
        "🟡 **Dengeli (MEDIUM):**\n"
        "   Max %2 risk, 5-10x kaldıraç\n\n"
        "🔴 **Agresif (HIGH):**\n"
        "   Max %5 risk, 20x+ kaldıraç\n\n"
        "Seçiminiz AI Coach tavsiyelerini etkiler:",
        parse_mode="Markdown",
        reply_markup=risk_level_keyboard()
    )


async def settings_risk_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risk profilini günceller."""
    query      = update.callback_query
    risk_level = query.data.replace("settings_risk_", "")
    import sqlite3
    from config import DATABASE_PATH
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "UPDATE users SET risk_level = ? WHERE id = ?",
            (risk_level, query.from_user.id)
        )
    labels = {"LOW": "Muhafazakâr 🟢", "MEDIUM": "Dengeli 🟡", "HIGH": "Agresif 🔴"}
    await query.answer(f"Risk profili: {labels.get(risk_level, risk_level)}", show_alert=True)
    await settings_menu_callback(update, context)


# ═══════════════════════════════════════════════
#  DEMO HESAP BAKIYE SIFIRLA
# ═══════════════════════════════════════════════

async def settings_reset_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Demo hesap bakiyesini sıfırlar."""
    query = update.callback_query
    await query.answer()

    await _safe_edit(query, 
        f"🔄 **DEMO HESAP SIFIRLA**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Bu işlem:\n"
        f"  ✓ Bakiyenizi ${INITIAL_BALANCE:,.0f}'a sıfırlar\n"
        f"  ✓ İşlem geçmişini temizler\n"
        f"  ✓ Açık pozisyonları kapatır\n"
        f"  ✓ P&L istatistiklerini sıfırlar\n\n"
        f"⚠️ **Bu işlem geri alınamaz!**\n\n"
        f"Devam etmek istiyor musunuz?",
        parse_mode="Markdown",
        reply_markup=confirm_reset_keyboard("balance")
    )


# ═══════════════════════════════════════════════
#  TÜM VERİ SİL (ÇOK KATMANLI ONAY)
# ═══════════════════════════════════════════════

async def settings_reset_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm veri silme uyarısı — 1. katman."""
    query = update.callback_query
    await query.answer()

    await _safe_edit(query, 
        f"🗑️ **TÜM VERİ SİL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ **ÖNEMLİ UYARI!**\n\n"
        f"Bu işlem AŞAĞIDAKİLERİN TAMAMINI siler:\n"
        f"  ❌ Tüm işlem geçmişi\n"
        f"  ❌ Tüm açık pozisyonlar\n"
        f"  ❌ Sinyal favorileri\n"
        f"  ❌ AI Coach öğrenme verileri\n"
        f"  ❌ P&L istatistikleri\n"
        f"  ❌ Demo hesap bakiyesi\n\n"
        f"✅ KORUNAN veriler:\n"
        f"  • Hesap giriş bilgileri\n\n"
        f"**Bu işlem KESİNLİKLE GERİ ALINAMAZ!**\n\n"
        f"Devam etmek istediğinize emin misiniz?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Evet, Devam Et", callback_data="reset_all_step2")],
            [InlineKeyboardButton("❌ İptal",           callback_data="menu_settings")],
        ])
    )


async def settings_reset_all_step2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm veri silme — 2. katman (son onay)."""
    query = update.callback_query
    await query.answer()

    context.user_data["awaiting_reset_confirm"] = True

    await _safe_edit(query, 
        f"🗑️ **SON ONAY GEREKLİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Onaylamak için tam olarak şunu yazın:\n\n"
        f"```\nSIFIRLA\n```\n\n"
        f"Veya iptal etmek için /start yazın.",
        parse_mode="Markdown"
    )


async def reset_confirm_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcı 'SIFIRLA' yazarsa tüm verileri siler."""
    if not context.user_data.get("awaiting_reset_confirm"):
        return

    if update.message.text.strip().upper() == "SIFIRLA":
        user_id = update.effective_user.id
        reset_user_data(user_id)
        context.user_data.clear()

        from keyboards import main_menu_keyboard
        await update.message.reply_text(
            f"✅ **TÜM VERİLER SİLİNDİ**\n\n"
            f"Demo hesabınız sıfırlandı.\n"
            f"Bakiye: **${INITIAL_BALANCE:,.2f}**\n\n"
            f"Yeni başlamak için /start yazın.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Yanlış onay kodu. Sıfırlama iptal edildi.\n"
            "/start ile devam edin."
        )
        context.user_data.clear()


async def reset_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bakiye sıfırlama onayı."""
    query    = update.callback_query
    await query.answer()

    reset_type = query.data.replace("reset_confirm_", "")
    user_id    = query.from_user.id

    if reset_type == "balance":
        reset_user_data(user_id)
        await _safe_edit(query, 
            f"✅ **Demo hesabınız sıfırlandı!**\n\n"
            f"Yeni bakiye: **${INITIAL_BALANCE:,.2f}**",
            parse_mode="Markdown",
            reply_markup=back_button("menu_settings", "◀️ Ayarlar")
        )


# ═══════════════════════════════════════════════
#  HANDLER KAYITLARI
# ═══════════════════════════════════════════════

def register_settings_handlers(app):
    """Ayar handler'larını kaydeder."""
    app.add_handler(CommandHandler("ayarlar", settings_menu_callback))
    app.add_handler(CallbackQueryHandler(settings_menu_callback,           pattern="^menu_settings$"))
    app.add_handler(CallbackQueryHandler(settings_notifications_callback,  pattern="^settings_notifications$"))
    app.add_handler(CallbackQueryHandler(notif_toggle_callback,            pattern="^notif_toggle_"))
    app.add_handler(CallbackQueryHandler(settings_leverage_callback,       pattern="^settings_leverage$"))
    app.add_handler(CallbackQueryHandler(settings_leverage_selected,       pattern="^settings_lev_"))
    app.add_handler(CallbackQueryHandler(settings_auto_tp_callback,        pattern="^settings_auto_tp$"))
    app.add_handler(CallbackQueryHandler(auto_tp_toggle_callback,          pattern="^auto_tp_"))
    app.add_handler(CallbackQueryHandler(settings_risk_callback,           pattern="^settings_risk$"))
    app.add_handler(CallbackQueryHandler(settings_risk_selected,           pattern="^settings_risk_"))
    app.add_handler(CallbackQueryHandler(settings_reset_balance_callback,  pattern="^settings_reset_balance$"))
    app.add_handler(CallbackQueryHandler(settings_reset_all_callback,      pattern="^settings_reset_all$"))
    app.add_handler(CallbackQueryHandler(settings_reset_all_step2_callback, pattern="^reset_all_step2$"))
    app.add_handler(CallbackQueryHandler(reset_confirm_callback,           pattern="^reset_confirm_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, reset_confirm_text_handler
    ))
    logger.info("✅ Settings handlers kayıtlandı.")
