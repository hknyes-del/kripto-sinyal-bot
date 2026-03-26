"""
╔══════════════════════════════════════════════════════════════╗
║ DOSYA 10: handlers/positions_handler.py — Pozisyon Yönetimi ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Pozisyon açma (Long/Short), kapatma, kısmi kapatma,
TP/SL yönetimi ve gerçek zamanlı P&L gösterimini yönetir.
Kullanıcıların demo hesap üzerinde işlem yapmasını sağlar.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ContextTypes, CommandHandler, CallbackQueryHandler,
                           MessageHandler, filters, ConversationHandler)

from config import TIMEZONE, EMOJI as E, SUPPORTED_PAIRS, LEVERAGE_OPTIONS, DEFAULT_MARGIN
from database import (get_user, create_position, get_active_positions,
                      get_position, close_position as db_close_position,
                      mark_tp_hit)
from keyboards import (positions_menu_keyboard, position_detail_keyboard,
                       close_position_confirm_keyboard, partial_close_keyboard,
                       tp_action_keyboard, direction_keyboard, leverage_keyboard,
                       margin_keyboard, pair_select_keyboard, back_button)
import asyncio
from utils.market_data import get_current_price, get_24h_ticker
from utils.calculations import (calculate_unrealized_pnl, calculate_position_size,
                                  calculate_liquidation_price, calculate_account_summary,
                                  format_pnl)

logger = logging.getLogger(__name__)

async def _safe_edit(query, text, parse_mode="Markdown", reply_markup=None):
    """Mesajı güvenli günceller — photo mesajı olsa bile çalışır."""
    try:
        await query.edit_message_text(
            text, parse_mode=parse_mode, reply_markup=reply_markup
        )
    except Exception:
        try:
            await query.edit_message_caption(
                text, parse_mode=parse_mode, reply_markup=reply_markup
            )
        except Exception:
            try:
                await query.message.reply_text(
                    text, parse_mode=parse_mode, reply_markup=reply_markup
                )
            except Exception:
                pass


async def _async_price(symbol: str):
    """Non-blocking fiyat çekme."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_current_price, symbol)

async def _async_ticker(symbol: str):
    """Non-blocking ticker çekme."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_24h_ticker, symbol)


# Conversation states
CHOOSE_PAIR, CHOOSE_DIRECTION, CHOOSE_LEVERAGE, CHOOSE_MARGIN, SET_TP_SL, CONFIRM = range(6)

# Geçici kullanıcı veri deposu (pozisyon açma akışı için)
_pending_positions: dict = {}


# ═══════════════════════════════════════════════
#  POZİSYON MENÜSÜ
# ═══════════════════════════════════════════════

async def positions_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aktif pozisyonlar ana menüsü."""
    query = update.callback_query
    await query.answer()

    user_id    = query.from_user.id
    positions  = get_active_positions(user_id)
    user       = get_user(user_id)

    if not positions:
        text = (
            f"💼 **AKTİF POZİSYONLAR**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📭 Şu anda açık pozisyonunuz yok.\n\n"
            f"Yeni bir pozisyon açmak için **➕ Yeni Pozisyon**'a tıklayın."
        )
    else:
        # Güncel fiyatları çek ve P&L hesapla
        pairs  = list(set(p["pair"] for p in positions))
        prices = {}
        for p in pairs:
            prices[p] = await _async_price(p) or 0
        summary = calculate_account_summary(user["balance"], positions, prices)

        pnl_em  = "💰" if summary["unrealized_pnl"] >= 0 else "🔴"
        text = (
            f"💼 **AKTİF POZİSYONLAR** ({len(positions)} adet)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Bakiye: **${summary['balance']:,.2f}**\n"
            f"📊 Equity: **${summary['equity']:,.2f}**\n"
            f"{pnl_em} Anlık P&L: **${summary['unrealized_pnl']:+.2f}**\n"
            f"🔐 Kullanılan Marjin: **${summary['used_margin']:,.2f}**\n"
            f"✅ Serbest Marjin: **${summary['free_margin']:,.2f}**\n"
            f"📉 Marjin Seviyesi: **%{summary['margin_level']:.0f}** "
            f"{summary['margin_color']}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Pozisyonlar:**\n"
        )

        for pos in positions:
            price  = prices.get(pos["pair"], pos["entry_price"])
            pnl    = calculate_unrealized_pnl(
                pos["direction"], pos["entry_price"], price,
                pos["position_size"], pos["leverage"]
            )
            d_em   = "📈" if pos["direction"] == "LONG" else "📉"
            p_em   = "💚" if pnl["pnl_dollar"] >= 0 else "❤️"
            sign   = "+" if pnl["pnl_dollar"] >= 0 else ""
            pair   = pos["pair"].replace("USDT", "/USDT")

            text += (
                f"\n{d_em} **{pair}** {pos['leverage']}x\n"
                f"   Giriş: ${pos['entry_price']:,.4f} → ${price:,.4f}\n"
                f"   {p_em} P&L: **{sign}${pnl['pnl_dollar']:,.2f}** "
                f"({sign}{pnl['roi_pct']:.2f}%)\n"
            )

    await _safe_edit(query, 
        text, parse_mode="Markdown", reply_markup=positions_menu_keyboard()
    )


# ═══════════════════════════════════════════════
#  POZİSYON LİSTESİ (Detaylı)
# ═══════════════════════════════════════════════

async def positions_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Her pozisyon için ayrı buton listesi."""
    query    = update.callback_query
    await query.answer()

    user_id   = query.from_user.id
    positions = get_active_positions(user_id)

    if not positions:
        await _safe_edit(query, 
            "📭 Açık pozisyon yok.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yeni Pozisyon", callback_data="pos_new")],
                [InlineKeyboardButton("◀️ Geri", callback_data="menu_positions")],
            ])
        )
        return

    buttons = []
    for pos in positions:
        price = await _async_price(pos["pair"]) or pos["entry_price"]
        pnl   = calculate_unrealized_pnl(
            pos["direction"], pos["entry_price"], price,
            pos["position_size"], pos["leverage"]
        )
        d_em = "📈" if pos["direction"] == "LONG" else "📉"
        p_em = "💚" if pnl["pnl_dollar"] >= 0 else "❤️"
        sign = "+" if pnl["pnl_dollar"] >= 0 else ""
        pair = pos["pair"].replace("USDT", "/USDT")

        buttons.append([
            InlineKeyboardButton(
                f"{d_em}{pair} {pos['leverage']}x | {p_em}{sign}${pnl['pnl_dollar']:,.2f}",
                callback_data=f"pos_detail_{pos['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔄 Yenile", callback_data="pos_list"),
        InlineKeyboardButton("◀️ Geri",   callback_data="menu_positions"),
    ])

    await _safe_edit(query, 
        f"💼 **POZİSYON SEÇİN** ({len(positions)} aktif)\n\nDetay için tıklayın:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ═══════════════════════════════════════════════
#  POZİSYON DETAYI
# ═══════════════════════════════════════════════

async def position_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tek pozisyon detay sayfası."""
    query = update.callback_query
    await query.answer()

    pos_id = int(query.data.replace("pos_detail_", ""))
    pos    = get_position(pos_id)

    if not pos:
        await _safe_edit(query, 
            "❌ Pozisyon bulunamadı.", reply_markup=back_button("pos_list")
        )
        return

    price  = await _async_price(pos["pair"]) or pos["entry_price"]
    pnl    = calculate_unrealized_pnl(
        pos["direction"], pos["entry_price"], price,
        pos["position_size"], pos["leverage"]
    )
    liq_p  = calculate_liquidation_price(pos["direction"], pos["entry_price"], pos["leverage"])

    d_em   = "📈" if pos["direction"] == "LONG" else "📉"
    p_em   = "💰" if pnl["pnl_dollar"] >= 0 else "🔴"
    sign   = "+" if pnl["pnl_dollar"] >= 0 else ""
    pair   = pos["pair"].replace("USDT", "/USDT")

    # TP durumları
    tp_status = []
    if pos["tp1"]:
        tp1_em = "✅" if pos["tp1_hit"] else "🔜"
        tp_status.append(f"{tp1_em} TP1: ${pos['tp1']:,.4f}")
    if pos["tp2"]:
        tp2_em = "✅" if pos["tp2_hit"] else "🔜"
        tp_status.append(f"{tp2_em} TP2: ${pos['tp2']:,.4f}")
    if pos["tp3"]:
        tp3_em = "✅" if pos["tp3_hit"] else "🔜"
        tp_status.append(f"{tp3_em} TP3: ${pos['tp3']:,.4f}")

    # Açılış süresi
    try:
        opened  = datetime.fromisoformat(pos["opened_at"])
        duration = datetime.utcnow() - opened
        hours   = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        dur_str = f"{hours}s {minutes}d"
    except:
        dur_str = "N/A"

    sl_val = pos.get("stop_loss")
    sl_str = f"${sl_val:,.4f}" if sl_val else "Ayarlanmadı"

    text = (
        f"💼 **POZİSYON DETAYI** #{pos_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{d_em} **{pair}** — {pos['direction']} {pos['leverage']}x\n\n"

        f"💰 **FİYATLAR:**\n"
        f"  Giriş: **${pos['entry_price']:,.4f}**\n"
        f"  Güncel: **${price:,.4f}**\n"
        f"  Tasfiye: 🚨 **${liq_p:,.4f}**\n\n"

        f"{p_em} **KAR/ZARAR:**\n"
        f"  Miktar: **{sign}${pnl['pnl_dollar']:,.2f}**\n"
        f"  Yüzde: **{sign}{pnl['roi_pct']:.2f}%** (kaldıraçlı)\n\n"

        f"📊 **POZİSYON:**\n"
        f"  Boyut: {pos['position_size']:.6f} coin\n"
        f"  Marjin: ${pos['margin_used']:,.2f}\n"
        f"  Kaldıraç: {pos['leverage']}x\n\n"

        f"🎯 **HEDEFLER:**\n"
        + "\n".join([f"  {s}" for s in tp_status]) + "\n\n"

        f"🛑 **Stop Loss:** **{sl_str}**\n\n"

        f"⏱ Açık Süre: **{dur_str}**\n"
        f"📅 Açılış: {pos['opened_at'][:16] if pos.get('opened_at') else 'N/A'}\n"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=position_detail_keyboard(pos_id)
    )


# ═══════════════════════════════════════════════
#  POZİSYON KAPATMA
# ═══════════════════════════════════════════════

async def close_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pozisyon kapatma onay sayfası."""
    query  = update.callback_query
    await query.answer()

    pos_id = int(query.data.replace("pos_close_", ""))
    pos    = get_position(pos_id)

    if not pos:
        await _safe_edit(query, "❌ Pozisyon bulunamadı.")
        return

    price  = await _async_price(pos["pair"]) or pos["entry_price"]
    pnl    = calculate_unrealized_pnl(
        pos["direction"], pos["entry_price"], price,
        pos["position_size"], pos["leverage"]
    )
    sign   = "+" if pnl["pnl_dollar"] >= 0 else ""
    pair   = pos["pair"].replace("USDT", "/USDT")

    text = (
        f"⚠️ **POZİSYON KAPATMA ONAYI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 **{pair}** {pos['direction']} {pos['leverage']}x\n\n"
        f"Kapatma fiyatı: **${price:,.4f}**\n"
        f"Tahmini P&L: **{sign}${pnl['pnl_dollar']:,.2f}** ({sign}{pnl['roi_pct']:.2f}%)\n\n"
        f"**Pozisyonu kapatmak istediğinize emin misiniz?**"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=close_position_confirm_keyboard(pos_id)
    )


async def close_position_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pozisyon kapatmayı onaylar ve çalıştırır."""
    query  = update.callback_query
    await query.answer("Pozisyon kapatılıyor...")

    pos_id = int(query.data.replace("pos_close_confirm_", ""))
    pos    = get_position(pos_id)

    if not pos:
        await _safe_edit(query, "❌ Pozisyon bulunamadı.")
        return

    close_price = await _async_price(pos["pair"]) or pos["entry_price"]

    # P&L hesapla
    from utils.calculations import calculate_realized_pnl
    pnl_data = calculate_realized_pnl(
        pos["direction"], pos["entry_price"], close_price,
        pos["position_size"], pos["margin_used"], pos["leverage"]
    )

    # Veritabanını güncelle
    result = db_close_position(
        position_id  = pos_id,
        close_price  = close_price,
        close_reason = "MANUAL",
        gross_pnl    = pnl_data["gross_pnl"],
        fees         = pnl_data["fees"],
    )

    sign = "+" if result["net_pnl"] >= 0 else ""
    em   = "🎉" if result["net_pnl"] >= 0 else "😔"
    pair = pos["pair"].replace("USDT", "/USDT")

    await _safe_edit(query, 
        f"{em} **POZİSYON KAPATILDI!**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 {pair} {pos['direction']} {pos['leverage']}x\n\n"
        f"Giriş: ${pos['entry_price']:,.4f}\n"
        f"Çıkış: ${close_price:,.4f}\n\n"
        f"💰 **Net P&L: {sign}${result['net_pnl']:,.2f}**\n"
        f"📈 ROI: **{sign}{result['roi_pct']:.2f}%**\n\n"
        f"Komisyon: -${pnl_data['fees']:.4f}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 P&L Raporu",    callback_data="menu_pnl")],
            [InlineKeyboardButton("◀️ Pozisyonlar",   callback_data="menu_positions")],
        ])
    )


# ═══════════════════════════════════════════════
#  POZİSYONDAN SİNYAL AÇMA (Sinyal -> Pozisyon)
# ═══════════════════════════════════════════════

async def signal_open_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sinyal mesajındaki 'Pozisyon Aç' butonu."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    sig_id  = int(query.data.replace("pos_open_", ""))

    from database import get_signal
    sig = get_signal(sig_id)

    if not sig:
        await _safe_edit(query, 
            "❌ Sinyal verisi bulunamadı veya süresi dolmuş.",
            reply_markup=back_button("menu_signals")
        )
        return

    # Sinyal verilerini doldur
    context.user_data.clear()
    context.user_data.update({
        "pair":          sig["pair"],
        "direction":     sig["direction"],
        "price":         await _async_price(sig["pair"]) or sig["entry_min"],
        "tp1":           sig["tp1"],
        "tp2":           sig["tp2"],
        "tp3":           sig["tp3"],
        "sl":            sig["stop_loss"],
        "signal_id":     sig_id,
        "step":          "leverage"
    })

    # Doğrudan kaldıraç seçimine git
    d_em = "📈 LONG (Alış)" if sig["direction"] == "LONG" else "📉 SHORT (Satış)"
    await _safe_edit(query, 
        f"➕ **SİNYALİ POZİSYONA DÖNÜŞTÜR**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Coin: **{sig['pair'].replace('USDT', '/USDT')}**\n"
        f"Yön: **{d_em}**\n\n"
        f"**Adım 3/4:** Kaldıraç seçin:\n\n"
        f"🟢=Düşük Risk | 🟡=Orta | 🔴=Yüksek | 💀=Maksimum",
        parse_mode="Markdown",
        reply_markup=leverage_keyboard("new_pos_lev")
    )


# ═══════════════════════════════════════════════
#  YENİ POZİSYON AÇMA AKIŞI
# ═══════════════════════════════════════════════

async def new_position_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yeni pozisyon açma akışını başlatır — Coin seçimi."""
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    context.user_data["step"] = "pair"

    await _safe_edit(query, 
        "➕ **YENİ POZİSYON AÇ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**Adım 1/4:** Coin çiftini seçin:",
        parse_mode="Markdown",
        reply_markup=pair_select_keyboard("new_pos_pair")
    )


async def new_position_pair_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Coin seçildi → Yön seçimine geç."""
    query = update.callback_query
    await query.answer()

    pair = query.data.replace("new_pos_pair_", "")
    context.user_data["pair"] = pair

    price   = await _async_price(pair) or 0
    ticker  = await _async_ticker(pair)
    change  = ticker["change_pct"] if ticker else 0
    sign    = "+" if change >= 0 else ""

    await _safe_edit(query, 
        f"➕ **YENİ POZİSYON AÇ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Seçilen: **{pair.replace('USDT', '/USDT')}**\n"
        f"Güncel Fiyat: **${price:,.4f}**\n"
        f"24s Değişim: {sign}{change:.2f}%\n\n"
        f"**Adım 2/4:** Yönü seçin:",
        parse_mode="Markdown",
        reply_markup=direction_keyboard()
    )


async def new_position_direction_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yön seçildi → Kaldıraç seçimine geç."""
    query     = update.callback_query
    await query.answer()

    direction = query.data.replace("new_pos_", "")
    context.user_data["direction"] = direction

    d_em = "📈 LONG (Alış)" if direction == "LONG" else "📉 SHORT (Satış)"

    await _safe_edit(query, 
        f"➕ **YENİ POZİSYON AÇ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Coin: **{context.user_data['pair'].replace('USDT', '/USDT')}**\n"
        f"Yön: **{d_em}**\n\n"
        f"**Adım 3/4:** Kaldıraç seçin:\n\n"
        f"🟢=Düşük Risk | 🟡=Orta | 🔴=Yüksek | 💀=Maksimum",
        parse_mode="Markdown",
        reply_markup=leverage_keyboard("new_pos_lev")
    )


async def new_position_leverage_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kaldıraç seçildi → Marjin seçimine geç."""
    query    = update.callback_query
    await query.answer()

    leverage = int(query.data.replace("new_pos_lev_", ""))
    context.user_data["leverage"] = leverage

    # Kaldıraç risk uyarısı
    risk_warnings = {
        50:  "⚠️ Yüksek Risk! %2 aleyhte hareket = %100 kayıp",
        100: "💀 Aşırı Risk! %1 aleyhte hareket = %100 kayıp",
    }
    warning = risk_warnings.get(leverage, "")

    await _safe_edit(query, 
        f"➕ **YENİ POZİSYON AÇ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Coin: **{context.user_data['pair'].replace('USDT', '/USDT')}**\n"
        f"Yön: **{context.user_data['direction']}**\n"
        f"Kaldıraç: **{leverage}x**\n"
        + (f"\n{warning}\n" if warning else "") +
        f"\n**Adım 4/4:** Marjin miktarı seçin (Kullanılacak $):",
        parse_mode="Markdown",
        reply_markup=margin_keyboard("new_pos_margin")
    )


async def new_position_margin_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marjin seçildi → Özet ve onay."""
    query  = update.callback_query
    await query.answer()

    margin = float(query.data.replace("new_pos_margin_", ""))
    context.user_data["margin"] = margin

    pair      = context.user_data["pair"]
    direction = context.user_data["direction"]
    leverage  = context.user_data["leverage"]
    price     = await _async_price(pair) or 0

    pos_data  = calculate_position_size(margin, leverage, price)
    liq_price = calculate_liquidation_price(direction, price, leverage)

    atr_approx = price * 0.015   # Yaklaşık %1.5 ATR
    
    # Eğer sinyalden gelmiyorsa (manuel ise) TP/SL hesapla
    if "tp1" not in context.user_data:
        if direction == "LONG":
            tp1 = price + atr_approx * 2
            tp2 = price + atr_approx * 4
            tp3 = price + atr_approx * 7
            sl  = price - atr_approx * 2
        else:
            tp1 = price - atr_approx * 2
            tp2 = price - atr_approx * 4
            tp3 = price - atr_approx * 7
            sl  = price + atr_approx * 2
        
        context.user_data.update({
            "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl
        })
    else:
        tp1 = context.user_data["tp1"]
        tp2 = context.user_data["tp2"]
        tp3 = context.user_data["tp3"]
        sl  = context.user_data["sl"]

    # Kaydet
    context.user_data.update({
        "price": price, "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl,
        "position_size": pos_data["coin_amount"]
    })

    d_em = "📈" if direction == "LONG" else "📉"
    text = (
        f"✅ **POZİSYON ÖZETI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{d_em} **{pair.replace('USDT', '/USDT')} {direction} {leverage}x**\n\n"
        f"💰 Giriş Fiyatı: **${price:,.4f}**\n"
        f"📊 Pozisyon Değeri: **${pos_data['position_value']:,.2f}**\n"
        f"💵 Kullanılan Marjin: **${margin:,.2f}**\n"
        f"🔢 Coin Miktarı: **{pos_data['coin_amount']:.6f}**\n\n"
        f"🎯 **HEDEFLER (ATR Bazlı):**\n"
        f"  TP1: ${tp1:,.4f} (+{abs(tp1-price)/price*100*leverage:.1f}%)\n"
        f"  TP2: ${tp2:,.4f} (+{abs(tp2-price)/price*100*leverage:.1f}%)\n"
        f"  TP3: ${tp3:,.4f} (+{abs(tp3-price)/price*100*leverage:.1f}%)\n\n"
        f"🛑 **Stop Loss:** ${sl:,.4f}\n"
        f"🚨 **Tasfiye Fiyatı:** ${liq_price:,.4f}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Pozisyonu açmak istiyor musunuz?"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ POZİSYONU AÇ", callback_data="pos_open_confirm")],
            [InlineKeyboardButton("❌ İptal",          callback_data="menu_positions")],
        ])
    )


async def confirm_open_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pozisyonu açar ve veritabanına kaydeder."""
    query   = update.callback_query
    await query.answer("Pozisyon açılıyor...")

    user_id = query.from_user.id
    data    = context.user_data

    user    = get_user(user_id)
    if user["balance"] < data["margin"]:
        await _safe_edit(query, 
            "❌ **Yetersiz bakiye!**\n\n"
            f"Gerekli: ${data['margin']:,.2f}\n"
            f"Mevcut: ${user['balance']:,.2f}",
            reply_markup=back_button("menu_positions")
        )
        return

    pos_id = create_position(
        user_id       = user_id,
        pair          = data["pair"],
        direction     = data["direction"],
        entry_price   = data["price"],
        position_size = data["position_size"],
        margin_used   = data["margin"],
        leverage      = data["leverage"],
        tp1           = data["tp1"],
        tp2           = data["tp2"],
        tp3           = data["tp3"],
        stop_loss     = data["sl"],
    )

    d_em = "📈" if data["direction"] == "LONG" else "📉"
    pair = data["pair"].replace("USDT", "/USDT")

    await _safe_edit(query, 
        f"🎉 **POZİSYON AÇILDI!**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{d_em} **{pair} {data['direction']} {data['leverage']}x**\n\n"
        f"Pozisyon ID: **#{pos_id}**\n"
        f"Giriş: **${data['price']:,.4f}**\n"
        f"Marjin: **${data['margin']:,.2f}**\n\n"
        f"TP1 / TP2 / TP3 seviyeleri ayarlandı.\n"
        f"Stop Loss ayarlandı.\n\n"
        f"⚡ Pozisyon izleniyor...",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📊 Pozisyon #{pos_id} Detayı", callback_data=f"pos_detail_{pos_id}")],
            [InlineKeyboardButton("💼 Tüm Pozisyonlar",            callback_data="pos_list")],
        ])
    )
    context.user_data.clear()


# ═══════════════════════════════════════════════
#  HANDLER KAYITLARI
# ═══════════════════════════════════════════════

def register_position_handlers(app):
    """Tüm pozisyon handler'larını kaydeder."""
    app.add_handler(CommandHandler("pozisyon", positions_menu_callback))
    app.add_handler(CallbackQueryHandler(positions_menu_callback,        pattern="^menu_positions$"))
    app.add_handler(CallbackQueryHandler(positions_list_callback,        pattern="^pos_list$"))
    app.add_handler(CallbackQueryHandler(position_detail_callback,       pattern="^pos_detail_"))
    app.add_handler(CallbackQueryHandler(close_position_callback,        pattern=r"^pos_close_\d+$"))
    app.add_handler(CallbackQueryHandler(close_position_confirm_callback, pattern="^pos_close_confirm_"))
    app.add_handler(CallbackQueryHandler(new_position_start,             pattern="^pos_new$"))
    app.add_handler(CallbackQueryHandler(signal_open_position_callback,  pattern=r"^pos_open_\d+$"))
    app.add_handler(CallbackQueryHandler(new_position_pair_selected,     pattern="^new_pos_pair_"))
    app.add_handler(CallbackQueryHandler(new_position_direction_selected, pattern="^new_pos_(LONG|SHORT)$"))
    app.add_handler(CallbackQueryHandler(new_position_leverage_selected, pattern="^new_pos_lev_"))
    app.add_handler(CallbackQueryHandler(new_position_margin_selected,   pattern=r"^new_pos_margin_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_open_position,          pattern="^pos_open_confirm$"))
    logger.info("✅ Position handlers kayıtlandı.")
