"""
╔══════════════════════════════════════════════════════════════╗
║   DOSYA 13: handlers/ai_coach_handler.py — AI Coach Modülü  ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Kullanıcının işlem geçmişini analiz eden, kişisel
performans içgörüleri üreten ve eğitim materyalleri sunan
AI Coach sistemini yönetir.
"""

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from config import TIMEZONE, EMOJI as E
from database import get_user, get_trade_history, get_user_stats, get_recent_signals
from keyboards import back_button, back_to_main
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
#  AI COACH ANA MENÜSÜ
# ═══════════════════════════════════════════════

async def ai_coach_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Coach ana menüsü."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user    = get_user(user_id)
    name    = query.from_user.first_name or "Trader"

    # Temel istatistikler
    stats_30 = get_user_stats(user_id, days=30)
    win_rate = stats_30.get("win_rate", 0)
    total_tr = stats_30.get("total_trades", 0) or 0

    # Seviye hesabı
    if total_tr < 10:
        level, level_em = "Başlangıç", "🌱"
    elif total_tr < 50:
        level, level_em = "Gelişen", "📈"
    elif total_tr < 100:
        level, level_em = "Deneyimli", "💹"
    else:
        level, level_em = "Uzman", "🏆"

    text = (
        f"🤖 **AI COACH**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Merhaba **{name}**! {level_em}\n"
        f"Seviyeniz: **{level}**\n\n"
        f"📊 **30 Günlük Özet:**\n"
        f"  İşlem: {total_tr} | Kazanma: %{win_rate:.1f}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Ne öğrenmek istersiniz?"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Performans Analizi",  callback_data="coach_analysis")],
            [InlineKeyboardButton("💡 Strateji Önerileri", callback_data="coach_strategy")],
            [InlineKeyboardButton("📚 Eğitim Merkezi",      callback_data="coach_education")],
            [InlineKeyboardButton("📈 Backtesting Sonuçları", callback_data="menu_backtest")],
            [InlineKeyboardButton("◀️ Ana Menü",            callback_data="menu_main")],
        ])
    )


# ═══════════════════════════════════════════════
#  PERFORMANS ANALİZİ
# ═══════════════════════════════════════════════

async def coach_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kişisel performans analizi ve öneriler."""
    query   = update.callback_query
    await query.answer("Analiz yapılıyor...")

    user_id = query.from_user.id
    trades  = get_trade_history(user_id, limit=100)
    stats   = calculate_pnl_statistics(trades)

    insights = []
    warnings = []

    if not trades:
        await _safe_edit(query, 
            "🤖 **PERFORMANS ANALİZİ**\n\n"
            "📭 Henüz kapatılmış işlem yok.\n\n"
            "İlk işleminizi açın ve AI Coach sizi izlemeye başlasın!",
            reply_markup=back_button("menu_ai_coach", "◀️ AI Coach")
        )
        return

    # ─── AI İçgörüler ────────────────────────────
    wr = stats["win_rate"]
    pf = stats["profit_factor"] if isinstance(stats["profit_factor"], float) else 99

    if wr >= 70:
        insights.append("🏆 Harika! %70+ kazanma oranı ile üst %15'tesiniz!")
    elif wr >= 55:
        insights.append("📈 İyi iş! Ortalama üzeri performans gösteriyorsunuz.")
    else:
        warnings.append(f"⚠️ Kazanma oranınız (%{wr:.1f}) ortalama altında. Strateji gözden geçirin.")

    if pf > 2:
        insights.append("💰 Profit Factor >2 mükemmel bir sistem göstergesi!")
    elif pf < 1:
        warnings.append("🔴 Profit Factor <1: Kaybettiğiniz, kazandığınızdan fazla!")

    if stats["max_lose_streak"] >= 5:
        warnings.append(f"⚠️ {stats['max_lose_streak']} ardışık kayıp tespit edildi! Duygusal trading riski var.")

    if stats["max_win_streak"] >= 5:
        insights.append(f"🔥 {stats['max_win_streak']} ardışık kazanma rekoru kırdınız!")

    if stats["avg_win"] > 0 and stats["avg_loss"] > 0:
        ratio = stats["avg_win"] / stats["avg_loss"]
        if ratio < 1:
            warnings.append(f"📉 Ort. kazancınız ({stats['avg_win']:.2f}$) ort. kayıptan ({stats['avg_loss']:.2f}$) küçük!")
        else:
            insights.append(f"✅ Risk/Reward iyi: Ort. kazanç/kayıp oranı {ratio:.2f}")

    text = (
        f"🤖 **PERFORMANS ANALİZİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 **{len(trades)} İşlem Analizi**\n\n"
    )

    if insights:
        text += "✅ **GÜÇLÜ YÖNLER:**\n"
        text += "\n".join([f"  {i}" for i in insights]) + "\n\n"

    if warnings:
        text += "⚠️ **GELİŞTİRİLECEKLER:**\n"
        text += "\n".join([f"  {w}" for w in warnings]) + "\n\n"

    # Tavsiyeler
    text += "💡 **AI TAVSİYELERİ:**\n"
    if wr < 60:
        text += "  • Giriş noktalarınızı daraltın, daha fazla onay bekleyin\n"
        text += "  • Sadece %85+ güvenli sinyallerle işlem yapın\n"
    if stats.get("max_lose_streak", 0) >= 3:
        text += "  • 3 ardışık kayıptan sonra 1 gün mola verin\n"
    if stats.get("total_trades", 0) > 5:
        text += f"  • En iyi performans: {_best_pair(trades)} üzerine odaklanın\n"

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=back_button("menu_ai_coach", "◀️ AI Coach")
    )


def _best_pair(trades: list) -> str:
    """En karlı coin çiftini bulur."""
    pair_pnl = {}
    for t in trades:
        pair = t["pair"].replace("USDT", "/USDT")
        pair_pnl[pair] = pair_pnl.get(pair, 0) + t.get("net_pnl", 0)
    if pair_pnl:
        return max(pair_pnl, key=pair_pnl.get)
    return "BTC/USDT"


# ═══════════════════════════════════════════════
#  STRATEJİ ÖNERİLERİ
# ═══════════════════════════════════════════════

async def coach_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kişisel strateji önerileri."""
    query   = update.callback_query
    await query.answer()

    user    = get_user(query.from_user.id)
    risk    = user.get("risk_level", "MEDIUM") if user else "MEDIUM"

    strategies = {
        "LOW": {
            "name": "🟢 Muhafazakâr Strateji",
            "desc": "Düşük riskli, istikrarlı büyüme",
            "items": [
                "Max 3x kaldıraç kullanın",
                "Sadece BTC ve ETH ile işlem yapın",
                "Her işlemde max %1 risk alın",
                "Günde 2-3 sinyalden fazla işlem açmayın",
                "Trend yönünde (EMA ile uyumlu) işlem yapın",
                "Haber öncesi pozisyon açmaktan kaçının",
            ]
        },
        "MEDIUM": {
            "name": "🟡 Dengeli Strateji",
            "desc": "Orta riskli, büyüme odaklı",
            "items": [
                "5-10x kaldıraç kullanın",
                "Top 5 coin ile işlem yapın",
                "Her işlemde max %2 risk alın",
                "MSB+FVG confluence bekleyin",
                "Multi-timeframe onayı alın (4H + 1H)",
                "TP1'de %30 kaparak riski sıfırlayın",
            ]
        },
        "HIGH": {
            "name": "🔴 Agresif Strateji",
            "desc": "Yüksek riskli, maksimum büyüme",
            "items": [
                "10-20x kaldıraç kullanabilirsiniz",
                "Altcoin'lerde fırsatlar arayın",
                "Her işlemde max %3-5 risk alın",
                "Haber katalizörlerini takip edin",
                "Kısa vadeli (15m-1H) scalping yapın",
                "Trailing stop kullanın",
            ]
        }
    }

    strat = strategies[risk]

    text = (
        f"💡 **STRATEJİ ÖNERİLERİ**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{strat['name']}\n"
        f"_{strat['desc']}_\n\n"
        f"**Kurallarınız:**\n"
    )
    for i, item in enumerate(strat["items"], 1):
        text += f"  {i}. {item}\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Risk profilinizi değiştirmek için:\n"
        f"Ayarlar → Risk Profili"
    )

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=back_button("menu_ai_coach", "◀️ AI Coach")
    )


# ═══════════════════════════════════════════════
#  EĞİTİM MERKEZİ
# ═══════════════════════════════════════════════

async def coach_education_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eğitim konuları menüsü."""
    query = update.callback_query
    await query.answer()

    await _safe_edit(query, 
        "📚 **EĞİTİM MERKEZİ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Öğrenmek istediğiniz konuyu seçin:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 MSB Nedir?",         callback_data="edu_msb")],
            [InlineKeyboardButton("📖 FVG Nedir?",         callback_data="edu_fvg")],
            [InlineKeyboardButton("📖 CRT Nedir?",         callback_data="edu_crt")],
            [InlineKeyboardButton("📖 Kaldıraç Rehberi",   callback_data="edu_leverage")],
            [InlineKeyboardButton("📖 Risk Yönetimi",      callback_data="edu_risk")],
            [InlineKeyboardButton("📖 RSI & MACD",         callback_data="edu_indicators")],
            [InlineKeyboardButton("◀️ AI Coach",           callback_data="menu_ai_coach")],
        ])
    )


async def edu_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eğitim konusu içeriği."""
    query = update.callback_query
    await query.answer()

    topics = {
        "edu_msb": (
            "📖 **MARKET STRUCTURE BREAK (MSB)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Tanım:** Fiyatın önceki önemli bir yüksek veya düşük seviyeyi kırmasıdır.\n\n"
            "**Bullish MSB:** 📈\n"
            "Fiyat son swing high'ı yukarı kırarsa → trend yukarı dönebiilr\n\n"
            "**Bearish MSB:** 📉\n"
            "Fiyat son swing low'u aşağı kırarsa → trend aşağı dönebilir\n\n"
            "**Nasıl Kullanılır?**\n"
            "1. Swing high/low noktalarını işaretleyin\n"
            "2. Kırılma anını bekleyin\n"
            "3. FVG ile confluence arayın\n"
            "4. Kırılma yönünde giriş yapın\n\n"
            "**💡 İpucu:** 4H ve 1H'i birlikte kullanın. Güçlü kırılmalar (>%1) daha güvenilirdir."
        ),
        "edu_fvg": (
            "📖 **FAIR VALUE GAP (FVG)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Tanım:** Fiyatın hızlı hareketiyle oluşan dolduruımamış boşluktur.\n\n"
            "**Bullish FVG:** 🟢\n"
            "3 ardışık mumda: Mum1.high < Mum3.low\n"
            "→ Destek bölgesi olarak işlev görür\n\n"
            "**Bearish FVG:** 🔴\n"
            "3 ardışık mumda: Mum1.low > Mum3.high\n"
            "→ Direnç bölgesi olarak işlev görür\n\n"
            "**Neden Önemli?**\n"
            "Kurumsal oyuncular bu boşlukları doldurmak için emir girer.\n"
            "Fiyat genellikle geri dönerek FVG'yi test eder.\n\n"
            "**MSB ile Kullanımı:**\n"
            "MSB + FVG = Yüksek olasılıklı giriş fırsatı 🎯"
        ),
        "edu_leverage": (
            "📖 **KALDIRAÇ REHBERI**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Kaldıraç = Sermayenizi çarpma kuvveti**\n\n"
            "Örnek: $100 marjin, 10x kaldıraç\n"
            "→ $1,000 değerinde pozisyon\n\n"
            "**Risk Tablosu:**\n"
            "```\nKaldıraç │ %1 Değişim │ Likidasyon\n"
            "─────────┼────────────┼──────────\n"
            "    1x   │    %1      │    -%100 \n"
            "    5x   │    %5      │    -%20  \n"
            "   10x   │   %10      │    -%10  \n"
            "   20x   │   %20      │     -%5  \n"
            "   50x   │   %50      │     -%2  \n```\n\n"
            "⚠️ Yüksek kaldıraç, küçük hareketlerde büyük kayıp!"
        ),
        "edu_risk": (
            "📖 **RİSK YÖNETİMİ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**Altın Kurallar:**\n\n"
            "1️⃣ Her işlemde max **%1-2 risk** al\n"
            "   $10,000 hesap → max $200 risk\n\n"
            "2️⃣ **Stop Loss KESİNLİKLE koy**\n"
            "   SL olmadan işlem = kumar\n\n"
            "3️⃣ **Risk/Reward en az 1:2 olsun**\n"
            "   $100 riske, $200+ kazanmayı hedefle\n\n"
            "4️⃣ **Eş zamanlı max %10 marjin** kullan\n"
            "   $10K hesap → max $1K açık pozisyon\n\n"
            "5️⃣ **3 ardışık kayıptan sonra dur**\n"
            "   Duygusal karar riski çok yüksek\n\n"
            "6️⃣ **Haber öncesi dikkat!**\n"
            "   FED, SEC haberleri volatiliteyi artırır"
        ),
    }

    topic_key = query.data
    content   = topics.get(topic_key, "Konu bulunamadı.")

    await _safe_edit(query, 
        content, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Eğitim Menüsü", callback_data="coach_education")],
            [InlineKeyboardButton("🏠 Ana Menü",       callback_data="menu_main")],
        ])
    )


# ═══════════════════════════════════════════════
#  BACKTEST SONUÇLARI
# ═══════════════════════════════════════════════

async def backtest_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Son 50 sinyalin backtest sonuçları."""
    query   = update.callback_query
    await query.answer()

    signals = get_recent_signals("NORMAL", limit=50)

    if not signals:
        await _safe_edit(query, 
            "📈 **BACKTESTING**\n\nHenüz sinyal geçmişi yok.",
            reply_markup=back_to_main()
        )
        return

    total   = len(signals)
    wins    = sum(1 for s in signals if s.get("outcome") == "WIN")
    losses  = sum(1 for s in signals if s.get("outcome") == "LOSS")
    pending = total - wins - losses
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

    text = (
        f"📈 **BACKTESTING SONUÇLARI**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Son **{total} Normal Sinyal** analizi:\n\n"
        f"✅ Kazanan: **{wins}** sinyal\n"
        f"❌ Kaybeden: **{losses}** sinyal\n"
        f"⏳ Bekleyen: **{pending}** sinyal\n\n"
        f"📊 **Win Rate: %{win_rate:.1f}**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Son 10 Sinyal:**\n\n"
    )

    for sig in signals[:10]:
        outcome = sig.get("outcome", "PENDING")
        out_em  = {"WIN": "✅", "LOSS": "❌", "PARTIAL": "🟡"}.get(outcome, "⏳")
        d_em    = "📈" if sig["direction"] == "LONG" else "📉"
        pair    = sig["pair"].replace("USDT", "/USDT")
        text += f"{out_em} {d_em} {pair} %{sig['confidence']:.0f} — {outcome}\n"

    await _safe_edit(query, 
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yenile",     callback_data="menu_backtest")],
            [InlineKeyboardButton("◀️ AI Coach",   callback_data="menu_ai_coach")],
            [InlineKeyboardButton("🏠 Ana Menü",   callback_data="menu_main")],
        ])
    )


def register_ai_coach_handlers(app):
    """AI Coach handler'larını kaydeder."""
    app.add_handler(CallbackQueryHandler(ai_coach_menu_callback,   pattern="^menu_ai_coach$"))
    app.add_handler(CallbackQueryHandler(coach_analysis_callback,  pattern="^coach_analysis$"))
    app.add_handler(CallbackQueryHandler(coach_strategy_callback,  pattern="^coach_strategy$"))
    app.add_handler(CallbackQueryHandler(coach_education_callback, pattern="^coach_education$"))
    app.add_handler(CallbackQueryHandler(edu_topic_callback,       pattern="^edu_"))
    app.add_handler(CallbackQueryHandler(backtest_menu_callback,   pattern="^menu_backtest$"))
    logger.info("✅ AI Coach handlers kayıtlandı.")
