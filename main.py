"""
╔══════════════════════════════════════════════════════════════╗
║           DOSYA 14: main.py — Ana Başlatıcı                  ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Botun ana giriş noktasıdır. Tüm handler'ları
kaydeder, veritabanını başlatır, zamanlayıcıyı kurar ve
botu Telegram ile polling modunda çalıştırır.
"""

import logging
import asyncio
from health_server import start_health_server
import os
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler

# ─── Konfigürasyon ─────────────────────────────
from config import (
    TELEGRAM_BOT_TOKEN, TIMEZONE,
    SIGNAL_GEN_INTERVAL, PRICE_CHECK_INTERVAL,
    SUPPORTED_PAIRS, EMOJI as E
)

# ─── Veritabanı ────────────────────────────────
from database import init_database, get_active_positions, get_user

# ─── Handler modülleri ─────────────────────────
from handlers.start_handler    import register_start_handlers
from handlers.signals_handler  import register_signal_handlers
from handlers.positions_handler import register_position_handlers
from handlers.pnl_handler      import register_pnl_handlers
from handlers.settings_handler import register_settings_handlers
from handlers.ai_coach_handler import register_ai_coach_handlers
from handlers.winrate_handler   import register_winrate_handlers
from handlers.dashboard_handler  import register_dashboard_handlers
from handlers.backtest_handler    import register_backtest_handlers, save_backtest_signal, update_backtest_results

# ─── Yardımcı modüller ─────────────────────────
from utils.market_data    import get_current_price
from utils.calculations   import calculate_unrealized_pnl, calculate_liquidation_price
from utils.signal_generator import scan_all_pairs_for_signals, format_signal_message, format_ai_message

# ─── Loglama ayarı ─────────────────────────────
logging.basicConfig(
    format  = "%(asctime)s | %(levelname)s | %(message)s",
    level   = logging.INFO,
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def _async_price(symbol: str):
    loop = asyncio.get_event_loop()
    from utils.market_data import get_current_price
    return await loop.run_in_executor(None, get_current_price, symbol)


# ═══════════════════════════════════════════════
#  ARKA PLAN GÖREVLERİ (APScheduler yerine basit async)
# ═══════════════════════════════════════════════

def _sl_sebep_analiz(pos: dict, close_price: float) -> str:
    """
    Stop loss sebebini analiz eder.
    Her stop yiyen işlem için otomatik etiket üretir.
    """
    try:
        direction    = pos.get("direction", "")
        entry        = pos.get("entry_price", 0)
        sl           = pos.get("stop_loss", 0)
        tp1          = pos.get("tp1", 0)
        duration_min = 0

        # İşlem süresini hesapla
        if pos.get("opened_at"):
            from datetime import datetime
            try:
                opened = datetime.fromisoformat(pos["opened_at"])
                duration_min = int((datetime.utcnow() - opened).total_seconds() / 60)
            except:
                pass

        risk = abs(entry - sl) if sl and entry else 0
        hareket = abs(close_price - entry)
        hareket_pct = hareket / entry * 100 if entry > 0 else 0

        # Sebep tespiti
        if duration_min < 30:
            return "⚡ Erken giriş — fiyat hemen döndü"

        if risk > 0 and hareket < risk * 0.3:
            return "📍 Stop çok dar — küçük dalgalanma yedi"

        if duration_min > 1440:  # 24 saatten uzun
            return "⏰ Zaman bazlı baskı — setup bayatladı"

        if direction == "LONG" and close_price < entry:
            if hareket_pct > 3:
                return "📉 Güçlü aşağı hareket — trend karşı çalıştı"
            else:
                return "🔄 Küçük geri çekilme — normal piyasa gürültüsü"

        if direction == "SHORT" and close_price > entry:
            if hareket_pct > 3:
                return "📈 Güçlü yukarı hareket — trend karşı çalıştı"
            else:
                return "🔄 Küçük yukarı sıçrama — normal piyasa gürültüsü"

        return "❓ Belirsiz — manuel inceleme önerilir"

    except Exception:
        return "❓ Analiz yapılamadı"


async def price_monitor_job(app: Application):
    """
    Her 30 saniyede çalışır.
    Açık pozisyonların fiyatlarını kontrol eder.
    TP/SL tetiklenirse kullanıcıya bildirim gönderir.
    """
    try:
        # Tüm aktif kullanıcıları bul
        import sqlite3
        from config import DATABASE_PATH
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute(
                "SELECT DISTINCT user_id FROM positions WHERE status='ACTIVE'"
            ).fetchall()

        for user_row in users:
            user_id   = user_row["user_id"]
            positions = get_active_positions(user_id)

            for pos in positions:
                price = await _async_price(pos["pair"])
                if not price:
                    continue

                # Backtest güncelle
                try:
                    update_backtest_results(pos["pair"], price)
                except Exception:
                    pass

                # P&L hesapla
                pnl = calculate_unrealized_pnl(
                    pos["direction"], pos["entry_price"], price,
                    pos["position_size"], pos["leverage"]
                )

                # Veritabanında güncelle (UI için her zaman güncel kalsın)
                from database import update_position_price
                update_position_price(pos["id"], price, pnl["pnl_dollar"])

                # ─── TP Kontrolleri ─────────────────
                d = pos["direction"]
                tp_checks = [
                    (1, pos["tp1"], pos["tp1_hit"]),
                    (2, pos["tp2"], pos["tp2_hit"]),
                    (3, pos["tp3"], pos["tp3_hit"]),
                ]

                for tp_num, tp_price, tp_hit in tp_checks:
                    if tp_price and not tp_hit:
                        hit = (d == "LONG"  and price >= tp_price) or \
                              (d == "SHORT" and price <= tp_price)

                        if hit:
                            from database import mark_tp_hit, partial_close_position, update_stop_loss
                            from utils.calculations import calculate_realized_pnl
                            mark_tp_hit(pos["id"], tp_num)

                            pair = pos["pair"].replace("USDT", "/USDT")
                            em   = "🎯" if tp_num < 3 else "🏆"

                            # Otomatik kısmi kapanış oranları
                            # TP1 → %50 kapat, TP2 → kalan %50'nin %50'si, TP3 → tamamı
                            close_pct_map = {1: 0.50, 2: 0.50, 3: 1.00}
                            close_pct = close_pct_map.get(tp_num, 0.50)

                            partial = partial_close_position(pos["id"], close_pct, tp_price, f"TP{tp_num}")
                            net_pnl = partial.get("net_pnl", 0)
                            sign    = "+" if net_pnl >= 0 else ""

                            # Stop loss güncelle
                            if tp_num == 1:
                                # TP1 gelince stop → entry'e çek
                                update_stop_loss(pos["id"], pos["entry_price"])
                                sl_msg = f"🔒 Stop loss entry'e çekildi: ${pos['entry_price']:,.4f}"
                            elif tp_num == 2:
                                # TP2 gelince stop → TP1'e çek
                                update_stop_loss(pos["id"], pos["tp1"])
                                sl_msg = f"🔒 Stop loss TP1'e çekildi: ${pos['tp1']:,.4f}"
                            else:
                                sl_msg = "✅ Pozisyon tamamen kapatıldı"

                            close_pct_display = int(close_pct * 100)

                            msg = (
                                f"{em} **TP{tp_num} HEDEFİNE ULAŞILDI!**\n\n"
                                f"📍 {pair} {pos['direction']} {pos['leverage']}x\n"
                                f"TP{tp_num}: ${tp_price:,.4f}\n\n"
                                f"💰 **%{close_pct_display} otomatik kapatıldı**\n"
                                f"Realize P&L: **{sign}${net_pnl:,.2f}**\n\n"
                                f"{sl_msg}"
                            )

                            try:
                                await app.bot.send_message(
                                    chat_id    = user_id,
                                    text       = msg,
                                    parse_mode = "Markdown",
                                )
                                logger.info(f"TP{tp_num} otomatik kapatıldı: {user_id} {pair} %{close_pct_display}")
                            except Exception as e:
                                logger.warning(f"TP bildirimi gönderilemedi: {e}")

                # ─── Trailing Stop — TP1'e %3 yaklaşınca stop entry'e çek ───
                if pos["tp1"] and not pos.get("tp1_hit"):
                    from database import update_stop_loss
                    tp1_price    = pos["tp1"]
                    entry_price  = pos["entry_price"]
                    current_sl   = pos.get("stop_loss")
                    tp1_dist     = abs(tp1_price - price)
                    tp1_total    = abs(tp1_price - entry_price)

                    # Fiyat TP1'e %3 veya daha yakınsa ve stop henüz entry'de değilse
                    if tp1_total > 0:
                        yakinslik = tp1_dist / tp1_total  # 0 = TP1'de, 1 = entry'de
                        sl_entry  = entry_price

                        if yakinslik <= 0.03 and current_sl != sl_entry:
                            update_stop_loss(pos["id"], sl_entry)
                            pair_tr = pos["pair"].replace("USDT", "/USDT")
                            try:
                                await app.bot.send_message(
                                    chat_id    = user_id,
                                    text       = (
                                        f"🔒 **TRAİLİNG STOP AKTİF**\n\n"
                                        f"📍 {pair_tr} {pos['direction']} {pos['leverage']}x\n"
                                        f"TP1'e %3 yaklaştı — Stop entry'e çekildi\n"
                                        f"Stop: ${sl_entry:,.4f} (Başa baş güvencesi)"
                                    ),
                                    parse_mode = "Markdown",
                                )
                                logger.info(f"Trailing stop aktif: {pair_tr} stop → entry")
                            except Exception as e:
                                logger.debug(f"Trailing stop bildirimi: {e}")

                # ─── Stop Loss Kontrolü ─────────────
                sl_price = pos.get("stop_loss")
                if sl_price:
                    sl_hit = (d == "LONG"  and price <= sl_price) or \
                             (d == "SHORT" and price >= sl_price)

                    if sl_hit:
                        from utils.calculations import calculate_realized_pnl
                        from database import close_position as db_close

                        pnl_data = calculate_realized_pnl(
                            pos["direction"], pos["entry_price"], price,
                            pos["position_size"], pos["margin_used"], pos["leverage"]
                        )
                        db_close(pos["id"], price, "SL", pnl_data["gross_pnl"], pnl_data["fees"])

                        pair = pos["pair"].replace("USDT", "/USDT")
                        sign = "+" if pnl_data["net_pnl"] >= 0 else ""

                        # Stop yeme sebebi analizi
                        sl_sebep = _sl_sebep_analiz(pos, price)

                        msg = (
                            f"🛑 **STOP LOSS TETİKLENDİ!**\n\n"
                            f"📍 {pair} {pos['direction']} {pos['leverage']}x\n\n"
                            f"SL Seviyesi: ${sl_price:,.4f}\n"
                            f"Kapanış Fiyatı: ${price:,.4f}\n\n"
                            f"💸 Net P&L: **{sign}${pnl_data['net_pnl']:,.2f}** "
                            f"({sign}{pnl_data['roi_pct']:.2f}%)\n"
                            f"Komisyon: -${pnl_data['fees']:.4f}\n\n"
                            f"🔍 **Stop Sebebi:** {sl_sebep}\n\n"
                            f"Pozisyon otomatik kapatıldı."
                        )

                        from keyboards import back_to_main
                        try:
                            await app.bot.send_message(
                                chat_id      = user_id,
                                text         = msg,
                                parse_mode   = "Markdown",
                                reply_markup = back_to_main(),
                            )
                            logger.info(f"SL bildirimi gönderildi: {user_id} {pair}")
                        except Exception as e:
                            logger.warning(f"SL bildirimi gönderilemedi: {e}")

                # ─── Margin Call Kontrolü ──────────
                user = get_user(user_id)
                if user:
                    from utils.calculations import calculate_account_summary
                    all_pos = get_active_positions(user_id)
                    prices  = {p["pair"]: await _async_price(p["pair"]) or p["entry_price"]
                               for p in all_pos}
                    summary = calculate_account_summary(user["balance"], all_pos, prices)

                    if summary["margin_level"] < 120 and user.get("notifications", 1):
                        try:
                            await app.bot.send_message(
                                chat_id    = user_id,
                                text       = (
                                    f"⚠️ **MARGIN CALL UYARISI!**\n\n"
                                    f"Marjin seviyeniz: **%{summary['margin_level']:.0f}**\n"
                                    f"Equity: ${summary['equity']:,.2f}\n"
                                    f"Kullanılan Marjin: ${summary['used_margin']:,.2f}\n\n"
                                    f"Lütfen pozisyon kapatın veya bakiye ekleyin!"
                                ),
                                parse_mode = "Markdown",
                            )
                        except Exception:
                            pass

    except Exception as e:
        logger.error(f"Price monitor hatası: {e}")

    # ─── Fiyat Alarmı Kontrolü ──────────────────────────────────
    try:
        from database import get_active_alarms, trigger_alarm
        alarms = get_active_alarms()

        for alarm in alarms:
            try:
                price = await _async_price(alarm["pair"])
                if not price:
                    continue

                entry_min = alarm["entry_min"]
                entry_max = alarm["entry_max"]

                # Fiyat giriş zonuna girdi mi?
                if entry_min <= price <= entry_max:
                    trigger_alarm(alarm["id"])

                    pair_display = alarm["pair"].replace("USDT", "/USDT")
                    direction    = alarm["direction"]
                    em           = "📈" if direction == "LONG" else "📉"

                    # Orijinal sinyal bilgilerini getir
                    from database import get_signal
                    signal_id = alarm.get("signal_id")
                    sig = get_signal(signal_id) if signal_id else None

                    if sig:
                        from utils.signal_generator import _fmt, format_ai_message
                        stars = "⭐" * min(int(sig.get("confidence", 0) // 20), 5)

                        # AI kararını al
                        try:
                            sig_dict = dict(sig) if not isinstance(sig, dict) else sig
                            sig_dict["current_price"] = price
                            ai_karar = format_ai_message(sig_dict)
                        except Exception:
                            ai_karar = ""

                        msg = (
                            f"🔔🔔🔔 **FİYAT ALARMI TETİKLENDİ!** 🔔🔔🔔\n"
                            f"{'━'*32}\n\n"
                            f"{'📈' if direction == 'LONG' else '📉'} **{pair_display} {direction}**\n"
                            f"⏰ Zaman: {sig.get('created_at','')}\n"
                            f"📊 Timeframe: {sig.get('timeframe','')}\n"
                            f"{stars} Güven: **%{sig.get('confidence',0):.0f}**\n\n"
                            f"💰 **Güncel Fiyat: ${_fmt(price)}**\n\n"
                            f"📍 **GİRİŞ ZONU:**\n"
                            f"   **${_fmt(entry_min)} — ${_fmt(entry_max)}**\n\n"
                            f"🎯 **HEDEFLER:**\n"
                            f"   TP1: ${_fmt(sig.get('tp1',0))}\n"
                            f"   TP2: ${_fmt(sig.get('tp2',0))}\n"
                            f"   TP3: ${_fmt(sig.get('tp3',0))}\n\n"
                            f"🛑 **STOP LOSS: ${_fmt(sig.get('stop_loss',0))}**\n"
                            f"📐 **Risk/Reward: 1:{sig.get('rr_ratio','N/A')}**\n"
                            f"{'━'*32}"
                            f"{ai_karar}"
                        )
                    else:
                        msg = (
                            f"🔔🔔🔔 **FİYAT ALARMI TETİKLENDİ!** 🔔🔔🔔\n"
                            f"{'━'*32}\n\n"
                            f"{em} **{pair_display} {direction}**\n\n"
                            f"💰 **Güncel Fiyat: ${_fmt(price)}**\n"
                            f"📍 **Giriş Zonu: ${_fmt(entry_min)} — ${_fmt(entry_max)}**\n"
                            f"{'━'*32}"
                        )

                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            "💼 Pozisyon Aç",
                            callback_data=f"pos_open_{signal_id}"
                        )]
                    ]) if signal_id else None

                    await app.bot.send_message(
                        chat_id      = alarm["user_id"],
                        text         = msg,
                        parse_mode   = "Markdown",
                        reply_markup = keyboard,
                    )
                    logger.info(f"🔔 Alarm tetiklendi: {alarm['pair']} ${price:.4f}")

            except Exception as e:
                logger.debug(f"Alarm kontrol hatası {alarm.get('pair')}: {e}")

    except Exception as e:
        logger.error(f"Alarm kontrol hatası: {e}")


async def signal_broadcast_job(app: Application):
    """
    Her 2 dakikada çalışır.
    3 sinyal tipini sırayla tarar: NORMAL, MSB_FVG, CRT
    Yeni sinyal bulunca tüm kullanıcılara iletir.
    """
    try:
        import sqlite3
        from config import DATABASE_PATH
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            users = conn.execute(
                "SELECT id FROM users WHERE notifications = 1"
            ).fetchall()

        if not users:
            return

        from keyboards import signal_detail_keyboard

        # ── 3 sinyal tipini sırayla tara ──────────────────────────────
        # Her turda sadece 1 tip taranır (CPU yükünü dağıtmak için)
        # NORMAL → MSB_FVG → CRT → NORMAL → ...
        if not hasattr(signal_broadcast_job, "_turn"):
            signal_broadcast_job._turn = 0

        turn_map = {0: "NORMAL", 1: "MSB_FVG", 2: "CRT"}
        signal_type = turn_map[signal_broadcast_job._turn % 3]
        signal_broadcast_job._turn += 1

        logger.info(f"🔍 Sinyal taraması: {signal_type}")
        # Taramayı thread'de çalıştır — botu bloklamaz
        loop = asyncio.get_event_loop()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as ex:
            signals = await loop.run_in_executor(
                ex, lambda: scan_all_pairs_for_signals(signal_type)
            )

        if not signals:
            logger.info(f"📭 {signal_type}: Sinyal yok")
            return

        # Max 2 sinyal yayınla (spam önlemi)
        for signal in signals[:2]:
            # Backtest'e kaydet
            try:
                save_backtest_signal(signal)
            except Exception as be:
                logger.debug(f"Backtest kayıt: {be}")
            msg = format_signal_message(signal)

            # Grafik oluştur (thread'de — botu bloklamaz)
            from utils.chart_generator import generate_signal_chart
            loop = asyncio.get_event_loop()

            chart_path = None
            chart_path_1d = None
            try:
                chart_path = await loop.run_in_executor(None, generate_signal_chart, signal)
            except Exception as ce:
                logger.debug(f"Grafik hatası: {ce}")

            # CRT için ayrıca 1D grafik
            if signal.get("type") == "CRT":
                try:
                    signal_1d = {**signal, "type": "CRT_1D"}  # 1D marker
                    chart_path_1d = await loop.run_in_executor(None, generate_signal_chart, signal_1d)
                except Exception as ce:
                    logger.debug(f"1D grafik hatası: {ce}")


            # Kısa grafik başlığı (sadece temel bilgi, 1024 sınırı için)
            pair_display = signal["pair"].replace("USDT", "/USDT")
            dir_em = "📈" if signal["direction"] == "LONG" else "📉"
            kisa_caption = (
                f"{dir_em} {signal.get('type','SİNYAL')} — {pair_display} {signal['direction']}\n"
                f"⭐ Güven: %{signal['confidence']:.0f} | R/R: 1:{signal.get('rr_ratio','?')}"
            )

            for user_row in users:
                try:
                    # Grafik varsa — kısa caption ile gönder
                    if chart_path and os.path.exists(chart_path):
                        with open(chart_path, "rb") as photo:
                            await app.bot.send_photo(
                                chat_id   = user_row["id"],
                                photo     = photo,
                                caption   = kisa_caption,
                                parse_mode = "Markdown",
                            )
                        # CRT ise 1D grafiği de gönder
                        if chart_path_1d and os.path.exists(chart_path_1d):
                            with open(chart_path_1d, "rb") as photo2:
                                await app.bot.send_photo(
                                    chat_id = user_row["id"],
                                    photo   = photo2,
                                    caption = "📅 1D Grafik",
                                )
                        await asyncio.sleep(0.3)

                    # Sinyal + AI kararları tek metin mesajı (4096 karakter sınırı — çok rahat)
                    await app.bot.send_message(
                        chat_id      = user_row["id"],
                        text         = msg[:4096],
                        parse_mode   = "Markdown",
                        reply_markup = signal_detail_keyboard(signal["id"], signal["pair"]),
                    )

                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.debug(f"Gönderilemedi {user_row['id']}: {e}")

            # Geçici dosyaları sil
            for p in [chart_path, chart_path_1d]:
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except: pass

        logger.info(f"📡 [{signal_type}] {len(signals)} sinyal → {len(users)} kullanıcı")

    except Exception as e:
        logger.error(f"Signal broadcast hatası: {e}")


async def signal_monitor_job(app: Application):
    """
    Tüm PENDING/ACTIVE sinyalleri izler. TP/SL durumuna göre günceller.
    Bu, backtest verilerinin doğru dolmasını sağlar.
    """
    try:
        import sqlite3
        from config import DATABASE_PATH
        from database import update_signal_status
        
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            signals = conn.execute(
                "SELECT * FROM signals WHERE status IN ('PENDING', 'ACTIVE')"
            ).fetchall()

        if not signals:
            return

        for sig in signals:
            pair = sig["pair"]
            price = await _async_price(pair)
            if not price: continue

            # SL Kontrolü
            is_sl_hit = False
            if sig["direction"] == "LONG"  and price <= sig["stop_loss"]: is_sl_hit = True
            if sig["direction"] == "SHORT" and price >= sig["stop_loss"]: is_sl_hit = True

            if is_sl_hit:
                update_signal_status(sig["id"], "SL", result_pnl=-10.0) # Temsili -10% veya gerçek hesaplanabilir
                continue

            # TP Kontrolü
            tp_hit = None
            if sig["direction"] == "LONG":
                if price >= sig["tp3"]: tp_hit = "TP3"
                elif price >= sig["tp2"]: tp_hit = "TP2"
                elif price >= sig["tp1"]: tp_hit = "TP1"
            else: # SHORT
                if price <= sig["tp3"]: tp_hit = "TP3"
                elif price <= sig["tp2"]: tp_hit = "TP2"
                elif price <= sig["tp1"]: tp_hit = "TP1"

            if tp_hit:
                # Basit bir P&L tahmini
                pnl = 5.0 if tp_hit == "TP1" else (10.0 if tp_hit == "TP2" else 20.0)
                update_signal_status(sig["id"], tp_hit, result_pnl=pnl)
                continue

            # Expiry Kontrolü
            from datetime import datetime
            try:
                valid_until = datetime.fromisoformat(sig["valid_until"])
                if datetime.utcnow() > valid_until:
                    update_signal_status(sig["id"], "EXPIRED", result_pnl=0.0)
            except:
                pass

    except Exception as e:
        logger.error(f"Signal monitor hatası: {e}")


# ═══════════════════════════════════════════════
#  DÖNGÜSEL GÖREV ÇALIŞTIRICISI
# ═══════════════════════════════════════════════

async def run_background_jobs(app: Application):
    """Arka plan görevlerini belirli aralıklarla çalıştırır."""
    logger.info("🔄 Arka plan görevleri başlatıldı.")

    # Health server başlat (UptimeRobot için)
    try:
        await start_health_server()
        logger.info("✅ Health server başlatıldı")
    except Exception as e:
        logger.warning(f"Health server başlatılamadı: {e}")
    
    # İlk çalıştırmayı hemen yap
    await price_monitor_job(app)
    await signal_broadcast_job(app)
    
    price_counter   = 30
    signal_counter  = 30
    monitor_counter = 30

    while True:
        await asyncio.sleep(30)
        price_counter   += 30
        signal_counter  += 30
        monitor_counter += 30

        # Fiyat + TP/SL kontrolü (Pozisyonlar için)
        if price_counter >= PRICE_CHECK_INTERVAL:
            await price_monitor_job(app)
            price_counter = 0

        # Sinyal taraması
        if signal_counter >= SIGNAL_GEN_INTERVAL:
            await signal_broadcast_job(app)
            signal_counter = 0
            
        # Sinyal izleme (Backtest için)
        if monitor_counter >= 300: # Her 5 dakikada bir sinyalleri güncelle
            await signal_monitor_job(app)
            monitor_counter = 0


# ═══════════════════════════════════════════════
#  BILINMEYEN CALLBACK HANDLER
# ═══════════════════════════════════════════════

async def unknown_callback(update: Update, _):
    """Tanımlanmamış callback sorgularını yakalar."""
    try:
        await update.callback_query.answer(
            "⚠️ Bu buton artık geçerli değil. /start ile yeniden başlayın.",
            show_alert=True
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════
#  ANA BAŞLATICI
# ═══════════════════════════════════════════════

def main():
    """Botu başlatır."""
    print("╔══════════════════════════════════╗")
    print("║  🚀 KRİPTO SİNYAL BOTU          ║")
    print("║  Başlatılıyor...                 ║")
    print("╚══════════════════════════════════╝")

    # 1. Veritabanını başlat
    init_database()

    # 2. Token kontrolü
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("❌ TELEGRAM_BOT_TOKEN ayarlanmamış! .env dosyasını düzenleyin.")
        print("\n❌ HATA: Bot token eksik!")
        print("📝 Çözüm: .env dosyasını oluşturun:")
        print("   TELEGRAM_BOT_TOKEN=your_token_from_botfather")
        return

    # 3. Telegram uygulamasını oluştur
    app = Application.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .connect_timeout(30) \
        .read_timeout(30) \
        .build()

    # 4. Handler'ları kaydet
    register_start_handlers(app)
    register_signal_handlers(app)
    register_position_handlers(app)
    register_pnl_handlers(app)
    register_settings_handlers(app)
    register_ai_coach_handlers(app)
    register_winrate_handlers(app)
    register_dashboard_handlers(app)
    register_backtest_handlers(app)

    # 5. Bilinmeyen callback yakalayıcı (en sona eklenmeli!)
    app.add_handler(CallbackQueryHandler(unknown_callback))

    # 6. Arka plan görevleri
    async def post_init(application: Application):
        asyncio.create_task(run_background_jobs(application))
        logger.info("✅ Arka plan görevleri başlatıldı.")
        
        # ─── Admin'e Başlangıç Bildirimi ─────
        from config import ADMIN_USER_IDS
        for admin_id in ADMIN_USER_IDS:
            try:
                await application.bot.send_message(
                    chat_id=admin_id,
                    text="🚀 **Bot Çevrimiçi!**\nSistem başarıyla başlatıldı ve bağlanıldı."
                )
                logger.info(f"Admin {admin_id} için başlangıç mesajı gönderildi.")
            except Exception as e:
                logger.warning(f"Admin {admin_id} için başlangıç mesajı gönderilemedi: {e}")

    app.post_init = post_init

    # 7. Botu başlat
    now_tr = datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")
    logger.info(f"✅ Bot başlatıldı — {now_tr} GMT+3")
    print(f"\n✅ Bot başlatıldı: {now_tr} GMT+3")
    print("📡 Telegram'a bağlanıyor...\n")
    print("Durdurmak için: CTRL+C\n")

    app.run_polling(
        allowed_updates = Update.ALL_TYPES,
        drop_pending_updates = True,
    )


if __name__ == "__main__":
    main()
