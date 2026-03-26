"""
handlers/backtest_handler.py — /backtest komutu
Her sinyal otomatik kaydedilir, TP/SL sonuçları takip edilir.
Girsen de girmesen de sistemin gerçek performansını gösterir.
"""

import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import DATABASE_PATH, TIMEZONE

logger = logging.getLogger(__name__)


def init_backtest_table():
    """Backtest tablosunu oluştur."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_signals (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id       INTEGER,
                    pair            TEXT NOT NULL,
                    direction       TEXT NOT NULL,
                    signal_type     TEXT,
                    timeframe       TEXT,
                    entry_min       REAL,
                    entry_max       REAL,
                    stop_loss       REAL,
                    tp1             REAL,
                    tp2             REAL,
                    tp3             REAL,
                    rr_ratio        REAL,
                    confidence      REAL,
                    entry_price     REAL,
                    status          TEXT DEFAULT 'OPEN',
                    result          TEXT,
                    close_price     REAL,
                    result_rr       REAL,
                    created_at      TEXT DEFAULT (datetime('now')),
                    closed_at       TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bt_status ON backtest_signals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bt_pair ON backtest_signals(pair)")
    except Exception as e:
        logger.error(f"Backtest tablo hatası: {e}")


def save_backtest_signal(signal: dict):
    """Gelen sinyali backtest tablosuna kaydet."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            # Aynı sinyal tekrar kaydedilmesin
            exists = conn.execute(
                "SELECT id FROM backtest_signals WHERE signal_id = ?",
                (signal.get("id"),)
            ).fetchone()
            if exists:
                return

            entry_price = (signal.get("entry_min", 0) + signal.get("entry_max", 0)) / 2

            conn.execute("""
                INSERT INTO backtest_signals
                    (signal_id, pair, direction, signal_type, timeframe,
                     entry_min, entry_max, stop_loss, tp1, tp2, tp3,
                     rr_ratio, confidence, entry_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.get("id"),
                signal.get("pair"),
                signal.get("direction"),
                signal.get("type"),
                signal.get("timeframe"),
                signal.get("entry_min"),
                signal.get("entry_max"),
                signal.get("stop_loss"),
                signal.get("tp1"),
                signal.get("tp2"),
                signal.get("tp3"),
                signal.get("rr_ratio"),
                signal.get("confidence"),
                entry_price,
                signal.get("created_at", datetime.utcnow().isoformat()),
            ))
        logger.debug(f"Backtest sinyal kaydedildi: {signal.get('pair')} {signal.get('direction')}")
    except Exception as e:
        logger.error(f"Backtest kayıt hatası: {e}")


def update_backtest_results(pair: str, price: float):
    """Fiyata göre açık backtest sinyallerini güncelle."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            signals = conn.execute(
                "SELECT * FROM backtest_signals WHERE status = 'OPEN' AND pair = ?",
                (pair,)
            ).fetchall()

            for sig in signals:
                d      = sig["direction"]
                sl     = sig["stop_loss"]
                tp1    = sig["tp1"]
                tp2    = sig["tp2"]
                tp3    = sig["tp3"]
                entry  = sig["entry_price"]
                risk   = abs(entry - sl) if sl and entry and abs(entry - sl) > 0 else 1

                status = None
                result = None
                rr     = None

                if d == "LONG":
                    if price <= sl:
                        status, result, rr = "SL", "LOSS", -1.0
                    elif price >= tp3:
                        status, result = "TP3", "WIN"
                        rr = round((price - entry) / risk, 2)
                    elif price >= tp2:
                        status, result = "TP2", "WIN"
                        rr = round((price - entry) / risk, 2)
                    elif price >= tp1:
                        status, result = "TP1", "WIN"
                        rr = round((price - entry) / risk, 2)
                else:  # SHORT
                    if price >= sl:
                        status, result, rr = "SL", "LOSS", -1.0
                    elif price <= tp3:
                        status, result = "TP3", "WIN"
                        rr = round((entry - price) / risk, 2)
                    elif price <= tp2:
                        status, result = "TP2", "WIN"
                        rr = round((entry - price) / risk, 2)
                    elif price <= tp1:
                        status, result = "TP1", "WIN"
                        rr = round((entry - price) / risk, 2)

                if status:
                    conn.execute("""
                        UPDATE backtest_signals
                        SET status = ?, result = ?, close_price = ?,
                            result_rr = ?, closed_at = datetime('now')
                        WHERE id = ?
                    """, (status, result, price, rr, sig["id"]))

    except Exception as e:
        logger.debug(f"Backtest güncelleme hatası {pair}: {e}")


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/backtest komutu — sistem sinyal performansı."""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            all_sigs  = conn.execute("SELECT * FROM backtest_signals ORDER BY created_at DESC").fetchall()
            open_sigs = conn.execute("SELECT * FROM backtest_signals WHERE status = 'OPEN'").fetchall()
            closed    = conn.execute("SELECT * FROM backtest_signals WHERE status != 'OPEN'").fetchall()

        if not all_sigs:
            await update.message.reply_text(
                "Henüz backtest verisi yok.\n"
                "Yarın sinyaller gelince otomatik kaydedilmeye başlar."
            )
            return

        total   = len(all_sigs)
        n_open  = len(open_sigs)
        n_closed = len(closed)

        wins   = [s for s in closed if s["result"] == "WIN"]
        losses = [s for s in closed if s["result"] == "LOSS"]
        wr     = len(wins) / n_closed * 100 if n_closed else 0

        # RR ortalaması
        rr_vals = [s["result_rr"] for s in wins if s["result_rr"]]
        avg_rr  = sum(rr_vals) / len(rr_vals) if rr_vals else 0

        # TP/SL dağılımı
        tp1_c = sum(1 for s in closed if s["status"] == "TP1")
        tp2_c = sum(1 for s in closed if s["status"] == "TP2")
        tp3_c = sum(1 for s in closed if s["status"] == "TP3")
        sl_c  = sum(1 for s in closed if s["status"] == "SL")

        # Sinyal tipi bazında
        tip_stats = {}
        for s in closed:
            tip = s["signal_type"] or "BILINMIYOR"
            if tip not in tip_stats:
                tip_stats[tip] = {"wins": 0, "total": 0}
            tip_stats[tip]["total"] += 1
            if s["result"] == "WIN":
                tip_stats[tip]["wins"] += 1

        tip_str = ""
        for tip, st in tip_stats.items():
            t_wr = st["wins"] / st["total"] * 100 if st["total"] else 0
            em = "🏆" if tip == "CRT" else "🎯" if tip == "MSB_FVG" else "🚀"
            tip_str += f"  {em} {tip}: {st['wins']}/{st['total']} = %{t_wr:.0f}\n"

        # Yön bazında
        long_c  = [s for s in closed if s["direction"] == "LONG"]
        short_c = [s for s in closed if s["direction"] == "SHORT"]
        long_wr  = sum(1 for s in long_c if s["result"] == "WIN") / len(long_c) * 100 if long_c else 0
        short_wr = sum(1 for s in short_c if s["result"] == "WIN") / len(short_c) * 100 if short_c else 0

        # Son 5 sonuçlanan sinyal
        son5 = sorted([s for s in closed], key=lambda x: x["closed_at"] or "", reverse=True)[:5]
        son5_str = ""
        for s in son5:
            em   = "✅" if s["result"] == "WIN" else "❌"
            pair = (s["pair"] or "?").replace("USDT", "")
            rr_s = f"R:{s['result_rr']:.1f}" if s["result_rr"] else ""
            son5_str += f"  {em} {pair} {s['direction']} → {s['status']} {rr_s}\n"

        wr_em = "🟢" if wr >= 50 else "🟡" if wr >= 35 else "🔴"

        ayrac = '─' * 32
        veri_yok_msg = "  Veri yok (yeni islemlerden dolacak)"
        henuz_yok_msg = "  Henuz yok"

        msg = (
            "📈 SİSTEM BACKTEST RAPORU\n"
            f"{ayrac}\n\n"
            "GENEL\n"
            f"  Toplam sinyal: {total}\n"
            f"  Sonuçlanan: {n_closed} | Açık: {n_open}\n"
            f"  {wr_em} Winrate: %{wr:.1f}\n"
            f"  Ort. R/R: 1:{avg_rr:.2f}\n\n"
            "TP/SL DAGILIMI\n"
            f"  TP1:{tp1_c} | TP2:{tp2_c} | TP3:{tp3_c} | SL:{sl_c}\n\n"
            "YON\n"
            f"  LONG: %{long_wr:.0f} ({len(long_c)} islem)\n"
            f"  SHORT: %{short_wr:.0f} ({len(short_c)} islem)\n\n"
            "SINYAL TIPI\n"
            f"{tip_str if tip_str else veri_yok_msg}\n"
            "SON 5 SONUC\n"
            f"{son5_str if son5_str else henuz_yok_msg}\n"
            f"{ayrac}\n"
            "NOT: Bu rapor sisteme giren TUM sinyalleri\n"
            "takip eder, sen girsen de girmesen de."
        )

        await update.message.reply_text(msg[:4096])

    except Exception as e:
        logger.error(f"Backtest rapor hatası: {e}")
        await update.message.reply_text(f"Hata: {e}")


def register_backtest_handlers(app):
    """Backtest handler'larını kaydeder."""
    init_backtest_table()
    app.add_handler(CommandHandler("backtest", backtest_command))
    logger.info("✅ Backtest handler kayıtlandı.")