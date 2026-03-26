"""
╔══════════════════════════════════════════════════════════════╗
║  DOSYA 9: handlers/signals_handler.py — Sinyal Yöneticisi   ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Normal sinyallerin, MSB+FVG ve CRT sinyallerinin
gösterilmesi, taranması ve kullanıcıya iletilmesi işlemlerini
yönetir. Her sinyal tipi için ayrı menü ve mesaj formatları.
"""

import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from config import TIMEZONE, EMOJI as E, SUPPORTED_PAIRS
from database import get_recent_signals
from keyboards import (
    signals_menu_keyboard, signal_detail_keyboard,
    back_to_main, back_button
)
from utils.signal_generator import (
    generate_normal_signal, generate_msb_fvg_signal,
    generate_crt_signal, format_signal_message, scan_all_pairs_for_signals
)
from utils.market_data import get_current_price
from utils.chart_generator import generate_signal_chart

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


async def _async_price(symbol: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_current_price, symbol)



# ═══════════════════════════════════════════════
#  ANA SİNYAL MENÜSÜ
# ═══════════════════════════════════════════════

async def signals_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Normal sinyaller ana menüsü."""
    query = update.callback_query
    await query.answer()

    # Son sinyallerin özeti
    recent = get_recent_signals("NORMAL", limit=5)
    count  = len(recent)
    last   = recent[0] if recent else None
    now_tr = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")

    text = (
        f"🚀 **NORMAL SİNYALLER**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {now_tr} GMT+3\n\n"
        f"📊 Son 24 saat: **{count} sinyal** üretildi\n"
    )

    if last:
        d_em = "📈" if last["direction"] == "LONG" else "📉"
        text += (
            f"\n🔔 **Son Sinyal:**\n"
            f"  {d_em} {last['pair'].replace('USDT','/USDT')} "
            f"{last['direction']} | %{last['confidence']:.0f} güven\n"
            f"  {last['created_at'][:16]}\n"
        )

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Aşağıdan seçim yapın:"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=signals_menu_keyboard()
    )


# ═══════════════════════════════════════════════
#  SİNYAL TARA — TEK COİN
# ═══════════════════════════════════════════════

async def scan_signal_for_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Belirli bir coin için sinyal tarar."""
    query = update.callback_query
    await query.answer("Taranıyor... ⏳")

    pair = query.data.replace("signal_pair_", "")

    loading_msg = await _safe_edit(query, 
        f"⏳ **{pair.replace('USDT', '/USDT')} taranıyor...**\n"
        f"RSI, MACD, EMA, MSB, FVG analiz ediliyor...",
        parse_mode="Markdown"
    )

    try:
        signal = generate_normal_signal(pair=pair, timeframe="1h")

        if signal:
            msg = format_signal_message(signal)
            await loading_msg.edit_text(
                msg,
                parse_mode="Markdown",
                reply_markup=signal_detail_keyboard(signal["id"], pair),
            )
        else:
            current = await _async_price(pair)
            await loading_msg.edit_text(
                f"🔍 **{pair.replace('USDT', '/USDT')} Analizi**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Güncel Fiyat: ${current:,.4f}\n\n"
                f"⚠️ Şu anda yüksek kaliteli bir sinyal tespit edilemedi.\n"
                f"Mevcut piyasa koşulları minimum %85 güven eşiğini karşılamıyor.\n\n"
                f"💡 **Öneri:** 4H veya 1D timeframe'i deneyin.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Tara", callback_data=f"signal_pair_{pair}")],
                    [InlineKeyboardButton("◀️ Geri", callback_data="menu_signals")],
                ])
            )
    except Exception as ex:
        logger.error(f"Sinyal tarama hatası: {ex}")
        await loading_msg.edit_text(
            f"❌ Tarama sırasında hata oluştu.\nLütfen tekrar deneyin.",
            reply_markup=back_button("menu_signals")
        )


# ═══════════════════════════════════════════════
#  TÜM COİNLERİ TARA
# ═══════════════════════════════════════════════

async def scan_all_pairs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm desteklenen coinleri tarar."""
    query = update.callback_query
    await query.answer("Tüm coinler taranıyor...")

    loading = await _safe_edit(query, 
        "⏳ **Tüm coinler taranıyor...**\n\n"
        "BTC, ETH, SOL, BNB, XRP, ADA...\n"
        "Bu işlem 15-30 saniye sürebilir.",
        parse_mode="Markdown"
    )

    try:
        signals = scan_all_pairs_for_signals("NORMAL")

        if not signals:
            await loading.edit_text(
                "🔍 **Tarama Tamamlandı**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ Şu anda %85+ güven seviyesinde sinyal bulunamadı.\n\n"
                "Piyasa nötr seyrediyor. Daha sonra tekrar kontrol edin.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Tara", callback_data="signal_scan_all")],
                    [InlineKeyboardButton("◀️ Ana Menü", callback_data="menu_main")],
                ])
            )
            return

        # Bulunan sinyalleri listele
        text = (
            f"🎯 **TARAMA SONUÇLARI**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ **{len(signals)} sinyal** bulundu!\n\n"
        )

        buttons = []
        for sig in signals[:8]:
            d_em  = "📈" if sig["direction"] == "LONG" else "📉"
            pair_label = sig["pair"].replace("USDT", "/USDT")
            text += (
                f"{d_em} **{pair_label}** — {sig['direction']}\n"
                f"   Güven: %{sig['confidence']:.0f} | "
                f"RR: 1:{sig.get('rr_ratio', '?')}\n\n"
            )
            buttons.append([
                InlineKeyboardButton(
                    f"{d_em} {pair_label} | %{sig['confidence']:.0f}",
                    callback_data=f"signal_detail_{sig['id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("🔄 Tekrar Tara", callback_data="signal_scan_all"),
            InlineKeyboardButton("◀️ Geri", callback_data="menu_signals"),
        ])

        await loading.edit_text(
            text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as ex:
        logger.error(f"Toplu tarama hatası: {ex}")
        await loading.edit_text("❌ Tarama hatası.", reply_markup=back_button("menu_signals"))


# ═══════════════════════════════════════════════
#  MSB+FVG MENÜSÜ VE TARAMA
# ═══════════════════════════════════════════════

async def msb_fvg_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MSB+FVG sinyal menüsü."""
    query = update.callback_query
    await query.answer()

    text = (
        f"🎯 **MSB+FVG SİNYALLERİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Market Structure Break + Fair Value Gap**\n\n"
        f"Bu bölüm kurumsal trading konseptlerine dayalı\n"
        f"yüksek doğruluklu kurulum noktalarını tespit eder.\n\n"
        f"📐 **Analiz Yöntemi:**\n"
        f"  1️⃣ 4H'de MSB (trend kırılması) tespit\n"
        f"  2️⃣ Kırılma yönünde FVG (boşluk) tanımla\n"
        f"  3️⃣ 1H ile çift timeframe onayı\n"
        f"  4️⃣ %85+ güven → Sinyal üret\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Coin seçin:"
    )

    buttons = []
    row = []
    for pair in SUPPORTED_PAIRS[:6]:
        label = pair.replace("USDT", "")
        row.append(InlineKeyboardButton(label, callback_data=f"msb_pair_{pair}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔄 Tüm Coinleri Tara", callback_data="msb_scan_all")])
    buttons.append([InlineKeyboardButton("◀️ Ana Menü", callback_data="menu_main")])

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def msb_fvg_scan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MSB+FVG sinyali tarar."""
    query = update.callback_query
    await query.answer("MSB+FVG analizi yapılıyor...")

    if query.data == "msb_scan_all":
        pair = None
    else:
        pair = query.data.replace("msb_pair_", "")

    loading = await _safe_edit(query, 
        f"⏳ **MSB+FVG Analizi**\n"
        f"Market Structure Break ve Fair Value Gap\n"
        f"tespit ediliyor... (4H + 1H)",
        parse_mode="Markdown"
    )

    try:
        signal = generate_msb_fvg_signal(pair=pair, timeframe="4h")

        if signal:
            msb = signal.get("msb", {})
            fvg = signal.get("fvg", {})

            extra = (
                f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔬 **DETAYLI ANALİZ:**\n"
                f"MSB: {msb.get('type', 'N/A')} ({msb.get('strength', 'N/A')})\n"
                f"MSB Seviyesi: ${msb.get('level', 0):,.4f}\n"
                f"MSB Kırılması: %{msb.get('break_pct', 0)}\n\n"
                f"FVG: {fvg.get('type', 'N/A')}\n"
                f"FVG Zonu: ${fvg.get('bottom', 0):,.4f} - ${fvg.get('top', 0):,.4f}\n"
                f"FVG Büyüklüğü: %{fvg.get('gap_pct', 0)}\n"
                f"FVG Bölgesinde: {'✅ Evet' if signal.get('in_fvg_zone') else '❌ Hayır'}\n"
            )

            msg = format_signal_message(signal) + extra

            await loading.edit_text(
                msg, parse_mode="Markdown",
                reply_markup=signal_detail_keyboard(signal["id"], signal["pair"])
            )
        else:
            pair_label = (pair or "Tüm coinler").replace("USDT", "/USDT")
            await loading.edit_text(
                f"🔍 **MSB+FVG Analizi: {pair_label}**\n\n"
                f"❌ Confluence kurulumu tespit edilemedi.\n\n"
                f"**Sebepler:**\n"
                f"• MSB ve FVG aynı yönde değil\n"
                f"• Güven eşiği (%85) karşılanmadı\n"
                f"• 4H + 1H onayı alınamadı\n\n"
                f"💡 Biraz sonra tekrar deneyin.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar", callback_data=query.data)],
                    [InlineKeyboardButton("◀️ Geri", callback_data="menu_msb_fvg")],
                ])
            )
    except Exception as ex:
        logger.error(f"MSB+FVG hatası: {ex}")
        await loading.edit_text("❌ Analiz hatası.", reply_markup=back_button("menu_msb_fvg"))


# ═══════════════════════════════════════════════
#  CRT MENÜSÜ
# ═══════════════════════════════════════════════

async def crt_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CRT analiz menüsü."""
    query = update.callback_query
    await query.answer()

    text = (
        f"🔷 **CRT ANALİZİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Confluence Rejection Trend**\n\n"
        f"Kurumsal piyasa aktörlerinin aktivitelerini\n"
        f"ve makro trend dönüşlerini tespit eder.\n\n"
        f"📊 **Analiz Katmanları:**\n"
        f"  📅 1 Günlük (1D) ana trend\n"
        f"  ⏰ 4 Saatlik (4H) ara trend\n"
        f"  📈 EMA hizalaması\n"
        f"  💹 RSI divergence\n"
        f"  📊 MACD momentum\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = []
    row = []
    for pair in SUPPORTED_PAIRS[:4]:
        label = pair.replace("USDT", "")
        row.append(InlineKeyboardButton(f"🔷 {label}", callback_data=f"crt_pair_{pair}"))
    buttons.append(row)
    buttons.append([InlineKeyboardButton("📊 Tüm Majörleri Tara", callback_data="crt_scan_all")])
    buttons.append([InlineKeyboardButton("◀️ Ana Menü", callback_data="menu_main")])

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def crt_scan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CRT sinyali tarar."""
    query = update.callback_query
    await query.answer("CRT analizi yapılıyor...")

    pair = None if query.data == "crt_scan_all" else query.data.replace("crt_pair_", "")

    loading = await _safe_edit(query, 
        "⏳ **CRT Analizi Yapılıyor...**\n1D + 4H timeframe analiz ediliyor...",
        parse_mode="Markdown"
    )

    try:
        signal = generate_crt_signal(pair=pair)

        if signal:
            msg = format_signal_message(signal)
            await loading.edit_text(
                msg, parse_mode="Markdown",
                reply_markup=signal_detail_keyboard(signal["id"], signal["pair"])
            )
        else:
            await loading.edit_text(
                "🔷 **CRT Analizi Sonucu**\n\n"
                "⚠️ Şu anda CRT kurulumu tespit edilemedi.\n"
                "1D ve 4H trendleri birbiriyle çelişiyor.\n\n"
                "💡 Günlük veya haftalık periyot için tekrar deneyin.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar", callback_data=query.data)],
                    [InlineKeyboardButton("◀️ Geri", callback_data="menu_crt")],
                ])
            )
    except Exception as ex:
        logger.error(f"CRT hatası: {ex}")
        await loading.edit_text("❌ Analiz hatası.", reply_markup=back_button("menu_crt"))


# ═══════════════════════════════════════════════
#  SİNYAL LİSTESİ
# ═══════════════════════════════════════════════

async def signal_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Son sinyalleri listeler."""
    query = update.callback_query
    await query.answer()

    signals = get_recent_signals(limit=10)

    if not signals:
        await _safe_edit(query, 
            "📋 **SON SİNYALLER**\n\nHenüz sinyal üretilmedi.",
            reply_markup=back_button("menu_signals")
        )
        return

    text = f"📋 **SON {len(signals)} SİNYAL**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []

    for sig in signals:
        d_em   = "📈" if sig["direction"] == "LONG" else "📉"
        status = sig.get("status", "PENDING")
        pair   = sig["pair"].replace("USDT", "/USDT")
        s_time = sig["created_at"][:16] if sig.get("created_at") else ""

        type_label = {"NORMAL": "🚀", "MSB_FVG": "🎯", "CRT": "🔷"}.get(sig["signal_type"], "📊")

        text += (
            f"{type_label} {d_em} **{pair}** {sig['direction']}\n"
            f"   Güven: %{sig['confidence']:.0f} | {s_time}\n"
            f"   Durum: {status}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                f"{d_em} {pair} %{sig['confidence']:.0f}",
                callback_data=f"signal_detail_{sig['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton("◀️ Geri", callback_data="menu_signals")])

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


# ═══════════════════════════════════════════════
#  GRAFİK ANALİZ
# ═══════════════════════════════════════════════



async def alarm_set_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fiyat alarmı kur butonu."""
    query = update.callback_query
    await query.answer()

    try:
        # callback: alarm_set_{signal_id}_{pair}
        parts = query.data.replace("alarm_set_", "").split("_", 1)
        signal_id = int(parts[0])
        pair = parts[1]

        from database import get_signal, create_price_alarm
        signal = get_signal(signal_id)

        if not signal:
            await query.answer("Sinyal bulunamadı!", show_alert=True)
            return

        alarm_id = create_price_alarm(
            user_id   = query.from_user.id,
            signal_id = signal_id,
            pair      = pair,
            direction = signal["direction"],
            entry_min = signal["entry_min"],
            entry_max = signal["entry_max"],
        )

        msg = (
            f"🔔 **Fiyat Alarmı Kuruldu!**\n\n"
            f"📍 {pair.replace('USDT', '/USDT')} {signal['direction']}\n"
            f"Giriş Zonu: ${signal['entry_min']:,.4f} — ${signal['entry_max']:,.4f}\n\n"
            f"Fiyat zona girince bildirim alacaksın! ✅"
        )
        await _safe_edit(query, msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Alarm set hatası: {e}")
        await query.answer("Hata oluştu!", show_alert=True)

async def signal_chart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sinyal detay sayfasındaki 'Grafik Analiz' butonu."""
    query = update.callback_query
    await query.answer("Grafik hazırlanıyor... 🎨")

    pair = query.data.replace("signal_chart_", "")
    
    try:
        # 1 saatlik standart teknik grafik oluştur
        chart_path = generate_signal_chart({"pair": pair, "type": "NORMAL", "direction": "LONG", "timeframe": "1h", "entry_min": 0, "entry_max": 0, "stop_loss": 0, "tp1": 0, "tp2": 0, "tp3": 0, "confidence": 0})
        
        if chart_path and os.path.exists(chart_path):
            # Grafiği gönder
            with open(chart_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption=f"📊 **{pair.replace('USDT', '/USDT')} - 1H Teknik Analiz**\n\n"
                            f"Göstergeler:\n"
                            f"• EMA 20 (Turkuaz)\n"
                            f"• EMA 50 (Sarı)\n"
                            f"• RSI 14 (Mor)\n\n"
                            f"⚠️ *Yatırım tavsiyesi değildir.*",
                    parse_mode="Markdown"
                )
            
            # Geçici dosyayı sil (opsiyonel, klasörde kalsın derseniz silmeyin)
            # os.remove(chart_path)
        else:
            await query.message.reply_text("❌ Grafik oluşturulamadı. Lütfen tekrar deneyin.")
            
    except Exception as e:
        logger.error(f"Grafik gönderme hatası: {e}")
        await query.message.reply_text("❌ Grafik hazırlanırken bir hata oluştu.")


# ═══════════════════════════════════════════════
#  SİNYAL DETAY SAYFASI
# ═══════════════════════════════════════════════

async def signal_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tek bir sinyalin detaylarını ve butonlarını gösterir."""
    query = update.callback_query
    await query.answer()

    sig_id = int(query.data.replace("signal_detail_", ""))
    
    from database import get_signal
    sig = get_signal(sig_id)

    if not sig:
        await _safe_edit(query, 
            "❌ Sinyal bulunamadı veya silinmiş.",
            reply_markup=back_button("menu_signals")
        )
        return

    # Sinyal mesajını formatla
    msg = format_signal_message(sig)
    
    # Detay butonlarını ekle
    await _safe_edit(query, 
        msg,
        parse_mode="Markdown",
        reply_markup=signal_detail_keyboard(sig_id, sig["pair"])
    )


# ═══════════════════════════════════════════════
#  HANDLER KAYITLARI
# ═══════════════════════════════════════════════

def register_signal_handlers(app):
    """Tüm sinyal handler'larını kaydeder."""
    app.add_handler(CommandHandler("sinyal", signals_menu_callback))
    app.add_handler(CallbackQueryHandler(signals_menu_callback,  pattern="^menu_signals$"))
    app.add_handler(CallbackQueryHandler(signal_detail_callback, pattern="^signal_detail_"))
    app.add_handler(CallbackQueryHandler(scan_signal_for_pair,   pattern="^signal_pair_"))
    app.add_handler(CallbackQueryHandler(scan_all_pairs_callback, pattern="^signal_scan_all$"))
    app.add_handler(CallbackQueryHandler(signal_list_callback,   pattern="^signal_list$"))
    app.add_handler(CallbackQueryHandler(msb_fvg_menu_callback,  pattern="^menu_msb_fvg$"))
    app.add_handler(CallbackQueryHandler(msb_fvg_scan_callback,  pattern="^msb_"))
    app.add_handler(CallbackQueryHandler(crt_menu_callback,      pattern="^menu_crt$"))
    app.add_handler(CallbackQueryHandler(crt_scan_callback,      pattern="^crt_"))
    app.add_handler(CallbackQueryHandler(signal_chart_callback,  pattern="^signal_chart_"))
    app.add_handler(CallbackQueryHandler(alarm_set_callback,      pattern="^alarm_set_"))
    logger.info("✅ Signal handlers kayıtlandı.")
