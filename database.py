"""
╔══════════════════════════════════════════════════════════════╗
║        DOSYA 2: database.py — SQLite Veritabanı Yöneticisi  ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya:  Tüm veritabanı tablolarını oluşturur, kullanıcı
verilerini, işlem geçmişlerini, sinyalleri ve ayarları
SQLite üzerinde yönetir. ORM kullanmadan saf SQL ile hız
ve şeffaflık sağlar.
"""

import sqlite3
import json
import numpy as np

class _NumpyEncoder(json.JSONEncoder):
    """numpy int/float tiplerini JSON'a çevirir."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)):  return obj.tolist()
        if isinstance(obj, (np.bool_,)):    return bool(obj)
        return super().default(obj)
import logging
from datetime import datetime
from contextlib import contextmanager
from config import DATABASE_PATH, INITIAL_BALANCE, DEFAULT_LEVERAGE, DEFAULT_MARGIN, TIMEZONE

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
#  CONTEXT MANAGER — Güvenli bağlantı yönetimi
# ═══════════════════════════════════════════════
@contextmanager
def get_db():
    """Veritabanı bağlantısını güvenli şekilde yönetir."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row   # Sütun isimiyle erişim
    conn.execute("PRAGMA journal_mode=WAL")   # Yazma performansı
    conn.execute("PRAGMA foreign_keys=ON")    # Foreign key desteği
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB Hatası: {e}")
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════
#  TABLO OLUŞTURMA — Tüm şema tek fonksiyonda
# ═══════════════════════════════════════════════
def init_database():
    """Tüm tabloları oluşturur (yoksa). Güvenli: tekrar çalıştırılabilir."""
    with get_db() as conn:
        # ──────────────────────────────────────
        #  1. KULLANICILAR TABLOSU
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY,       -- Telegram user_id
            username         TEXT,
            first_name       TEXT,
            balance          REAL    DEFAULT 10000.0,   -- Hesap bakiyesi ($)
            initial_balance  REAL    DEFAULT 10000.0,
            total_pnl        REAL    DEFAULT 0.0,       -- Toplam kar/zarar
            default_leverage INTEGER DEFAULT 5,
            default_margin   REAL    DEFAULT 20.0,
            risk_level       TEXT    DEFAULT 'MEDIUM',  -- LOW / MEDIUM / HIGH
            notifications    INTEGER DEFAULT 1,         -- 0=kapalı 1=açık
            preferred_pairs  TEXT    DEFAULT '["BTCUSDT","ETHUSDT"]',
            timezone         TEXT    DEFAULT 'Europe/Istanbul',
            language         TEXT    DEFAULT 'TR',
            created_at       TEXT    DEFAULT (datetime('now')),
            last_active      TEXT    DEFAULT (datetime('now'))
        )
        """)

        # ──────────────────────────────────────
        #  2. POZİSYONLAR TABLOSU
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            pair            TEXT    NOT NULL,           -- örn: BTCUSDT
            direction       TEXT    NOT NULL,           -- LONG / SHORT
            entry_price     REAL    NOT NULL,
            current_price   REAL,
            position_size   REAL    NOT NULL,           -- Coin miktarı
            margin_used     REAL    NOT NULL,           -- Kullanılan marjin ($)
            leverage        INTEGER NOT NULL,
            
            -- Take Profit seviyeleri
            tp1             REAL,
            tp2             REAL,
            tp3             REAL,
            tp1_pct         REAL    DEFAULT 30.0,       -- TP1'de kapatılacak %
            tp2_pct         REAL    DEFAULT 40.0,
            tp3_pct         REAL    DEFAULT 30.0,
            tp1_hit         INTEGER DEFAULT 0,           -- 0=hayır, 1=evet
            tp2_hit         INTEGER DEFAULT 0,
            tp3_hit         INTEGER DEFAULT 0,
            
            -- Stop Loss
            stop_loss       REAL,
            trailing_stop   INTEGER DEFAULT 0,          -- 0=kapalı, 1=açık
            
            -- Durum
            status          TEXT    DEFAULT 'ACTIVE',   -- ACTIVE/CLOSED/LIQUIDATED
            close_price     REAL,
            close_reason    TEXT,                        -- TP1/TP2/TP3/SL/MANUAL
            gross_pnl       REAL    DEFAULT 0.0,
            fees            REAL    DEFAULT 0.0,
            net_pnl         REAL    DEFAULT 0.0,
            
            -- Sinyal referansı
            signal_id       INTEGER,
            
            -- Zaman damgaları
            opened_at       TEXT    DEFAULT (datetime('now')),
            closed_at       TEXT,
            
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # ──────────────────────────────────────
        #  3. SİNYALLER TABLOSU
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_type     TEXT    NOT NULL,           -- NORMAL/MSB_FVG/CRT/AI
            pair            TEXT    NOT NULL,
            direction       TEXT    NOT NULL,           -- LONG/SHORT
            timeframe       TEXT    DEFAULT '1h',
            
            -- Fiyat seviyeleri
            entry_min       REAL    NOT NULL,
            entry_max       REAL    NOT NULL,
            stop_loss       REAL    NOT NULL,
            tp1             REAL    NOT NULL,
            tp2             REAL,
            tp3             REAL,
            rr_ratio        REAL,                       -- Risk/Reward oranı
            
            -- Analiz
            confidence      REAL    DEFAULT 85.0,       -- Güven skoru (0-100)
            indicators      TEXT,                       -- JSON: kullanılan göstergeler
            analysis_text   TEXT,                       -- İnsan okunabilir analiz
            
            -- Sonuç
            status          TEXT    DEFAULT 'PENDING',  -- PENDING/ACTIVE/TP1/TP2/TP3/SL/EXPIRED
            result_pnl      REAL,
            outcome         TEXT,                       -- WIN/LOSS/PARTIAL
            
            -- Geçerlilik
            valid_until     TEXT,
            expires_in_hours INTEGER DEFAULT 8,
            
            -- Zaman damgaları
            created_at      TEXT    DEFAULT (datetime('now')),
            triggered_at    TEXT,
            closed_at       TEXT
        )
        """)

        # ──────────────────────────────────────
        #  4. İŞLEM GEÇMİŞİ TABLOSU (Kapatılan pozisyonlar)
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            position_id     INTEGER,
            pair            TEXT    NOT NULL,
            direction       TEXT    NOT NULL,
            
            -- Fiyatlar
            entry_price     REAL    NOT NULL,
            exit_price      REAL    NOT NULL,
            
            -- Miktar & Finansal
            position_size   REAL    NOT NULL,
            margin_used     REAL    NOT NULL,
            leverage        INTEGER NOT NULL,
            gross_pnl       REAL    NOT NULL,
            fees            REAL    DEFAULT 0.0,
            net_pnl         REAL    NOT NULL,
            roi_pct         REAL    NOT NULL,           -- % getiri
            
            -- Hedefler
            tp1_reached     INTEGER DEFAULT 0,
            tp2_reached     INTEGER DEFAULT 0,
            tp3_reached     INTEGER DEFAULT 0,
            sl_reached      INTEGER DEFAULT 0,
            close_reason    TEXT,
            
            -- Metadata
            signal_source   TEXT    DEFAULT 'MANUAL',
            timeframe       TEXT,
            duration_mins   INTEGER,                    -- İşlem süresi (dakika)
            
            -- Zaman damgaları
            opened_at       TEXT    NOT NULL,
            closed_at       TEXT    DEFAULT (datetime('now')),
            
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # ──────────────────────────────────────
        #  5. AI COACH NOTLARI
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_coach_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            note_type   TEXT    NOT NULL,   -- SUGGESTION/WARNING/INSIGHT/ACHIEVEMENT
            title       TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            is_read     INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # ──────────────────────────────────────
        #  6. BACKTESTING SONUÇLARI
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id       INTEGER NOT NULL,
            pair            TEXT    NOT NULL,
            direction       TEXT    NOT NULL,
            entry_price     REAL    NOT NULL,
            exit_price      REAL,
            stop_loss       REAL,
            tp1             REAL,
            tp2             REAL,
            tp3             REAL,
            outcome         TEXT,           -- WIN/LOSS/PARTIAL/PENDING
            pnl_pct         REAL,           -- % kar/zarar
            created_at      TEXT    DEFAULT (datetime('now')),
            closed_at       TEXT,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
        """)

        # ──────────────────────────────────────
        #  7. KULLANICI AYARLARI
        # ──────────────────────────────────────
        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id         INTEGER PRIMARY KEY,
            auto_tp_close   INTEGER DEFAULT 0,      -- TP'de otomatik kapat
            sound_alerts    INTEGER DEFAULT 1,
            email_alerts    INTEGER DEFAULT 0,
            min_confidence  INTEGER DEFAULT 85,     -- Minimum sinyal güveni
            max_positions   INTEGER DEFAULT 10,
            daily_loss_limit REAL   DEFAULT 200.0,
            show_chart      INTEGER DEFAULT 1,
            compact_view    INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # Fiyat alarmları tablosu
        conn.execute("""
        CREATE TABLE IF NOT EXISTS price_alarms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            signal_id   INTEGER,
            pair        TEXT    NOT NULL,
            direction   TEXT    NOT NULL,   -- LONG veya SHORT
            entry_min   REAL    NOT NULL,
            entry_max   REAL    NOT NULL,
            status      TEXT    DEFAULT 'ACTIVE',  -- ACTIVE, TRIGGERED, CANCELLED
            created_at  DATETIME DEFAULT (datetime('now')),
            triggered_at DATETIME
        )
        """)

        # İndeksler — Sorgu hızı için
        conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON trade_history(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type, status)")

    logger.info("✅ Veritabanı başlatıldı.")
    print("✅ Veritabanı tabloları oluşturuldu.")


# ═══════════════════════════════════════════════
#  KULLANICI FONKSİYONLARI
# ═══════════════════════════════════════════════

def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    """Kullanıcıyı getirir, yoksa oluşturur."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if user is None:
            conn.execute("""
            INSERT INTO users (id, username, first_name, balance, initial_balance)
            VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, INITIAL_BALANCE, INITIAL_BALANCE))

            conn.execute("""
            INSERT INTO user_settings (user_id) VALUES (?)
            """, (user_id,))

            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        else:
            # Son aktif zamanı güncelle
            conn.execute(
                "UPDATE users SET last_active = datetime('now') WHERE id = ?",
                (user_id,)
            )

        return dict(user)


def get_user(user_id: int) -> dict | None:
    """Kullanıcıyı getirir."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_balance(user_id: int, new_balance: float):
    """Kullanıcı bakiyesini günceller."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (round(new_balance, 2), user_id)
        )


def get_user_settings(user_id: int) -> dict:
    """Kullanıcı ayarlarını getirir."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else {}


def update_user_settings(user_id: int, **kwargs):
    """Kullanıcı ayarlarını günceller."""
    if not kwargs:
        return
    fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE user_settings SET {fields} WHERE user_id = ?", values
        )


# ═══════════════════════════════════════════════
#  POZİSYON FONKSİYONLARI
# ═══════════════════════════════════════════════

def create_position(user_id: int, pair: str, direction: str, entry_price: float,
                    position_size: float, margin_used: float, leverage: int,
                    tp1: float = None, tp2: float = None, tp3: float = None,
                    stop_loss: float = None, signal_id: int = None) -> int:
    """Yeni pozisyon oluşturur. Oluşturulan pozisyonun ID'sini döndürür."""
    with get_db() as conn:
        cursor = conn.execute("""
        INSERT INTO positions
            (user_id, pair, direction, entry_price, current_price, position_size,
             margin_used, leverage, tp1, tp2, tp3, stop_loss, signal_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, pair, direction, entry_price, entry_price,
              position_size, margin_used, leverage,
              tp1, tp2, tp3, stop_loss, signal_id))

        # Kullanıcı bakiyesini düş
        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (margin_used, user_id)
        )
        return cursor.lastrowid


def get_active_positions(user_id: int) -> list:
    """Kullanıcının aktif pozisyonlarını getirir."""
    with get_db() as conn:
        rows = conn.execute("""
        SELECT * FROM positions
        WHERE user_id = ? AND status = 'ACTIVE'
        ORDER BY opened_at DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_position(position_id: int) -> dict | None:
    """Tek bir pozisyonu getirir."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        ).fetchone()
        return dict(row) if row else None


def get_signal(signal_id: int) -> dict | None:
    """Tek bir sinyali getirir."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM signals WHERE id = ?", (signal_id,)
        ).fetchone()
        return dict(row) if row else None


def update_position_price(position_id: int, current_price: float, unrealized_pnl: float):
    """Pozisyonun güncel fiyatını ve kar/zararını günceller."""
    with get_db() as conn:
        conn.execute("""
        UPDATE positions
        SET current_price = ?, gross_pnl = ?
        WHERE id = ?
        """, (current_price, unrealized_pnl, position_id))



def _get_signal_source(conn, pos: dict) -> str:
    """Pozisyonun signal_id'sine bakarak sinyal tipini döner."""
    signal_id = pos.get("signal_id")
    if not signal_id:
        return "MANUAL"
    try:
        row = conn.execute(
            "SELECT signal_type FROM signals WHERE id = ?", (signal_id,)
        ).fetchone()
        if row:
            return row[0]  # NORMAL, MSB_FVG, CRT
    except:
        pass
    return "SIGNAL"

def close_position(position_id: int, close_price: float, close_reason: str,
                   gross_pnl: float, fees: float) -> dict:
    """Pozisyonu kapatır ve trade_history'ye ekler."""
    net_pnl = gross_pnl - fees
    with get_db() as conn:
        pos = dict(conn.execute(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        ).fetchone())

        conn.execute("""
        UPDATE positions
        SET status      = 'CLOSED',
            close_price = ?,
            close_reason = ?,
            gross_pnl   = ?,
            fees        = ?,
            net_pnl     = ?,
            closed_at   = datetime('now')
        WHERE id = ?
        """, (close_price, close_reason, gross_pnl, fees, net_pnl, position_id))

        # Kullanıcı bakiyesine marjin + kar/zarar ekle
        conn.execute("""
        UPDATE users
        SET balance   = balance + ? + ?,
            total_pnl = total_pnl + ?
        WHERE id = ?
        """, (pos["margin_used"], net_pnl, net_pnl, pos["user_id"]))

        # Trade history'ye kaydet
        duration = 0
        if pos.get("opened_at"):
            try:
                opened = datetime.fromisoformat(pos["opened_at"])
                duration = int((datetime.utcnow() - opened).total_seconds() / 60)
            except:
                pass

        roi_pct = (net_pnl / pos["margin_used"] * 100) if pos["margin_used"] > 0 else 0

        conn.execute("""
        INSERT INTO trade_history
            (user_id, position_id, pair, direction, entry_price, exit_price,
             position_size, margin_used, leverage, gross_pnl, fees, net_pnl,
             roi_pct, close_reason, signal_source, opened_at, duration_mins)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pos["user_id"], position_id, pos["pair"], pos["direction"],
              pos["entry_price"], close_price, pos["position_size"],
              pos["margin_used"], pos["leverage"], gross_pnl, fees, net_pnl,
              round(roi_pct, 2), close_reason,
              _get_signal_source(conn, pos),
              pos.get("opened_at"), duration))

    return {"net_pnl": net_pnl, "roi_pct": roi_pct}


def partial_close_position(position_id: int, close_pct: float, close_price: float, reason: str) -> dict:
    """
    Pozisyonun belirli yüzdesini kapatır.
    close_pct: 0.0 - 1.0 arası (örn: 0.5 = %50)
    Kalan pozisyonu günceller, kapatılan kısmı trade_history'ye ekler.
    """
    with get_db() as conn:
        pos = dict(conn.execute(
            "SELECT * FROM positions WHERE id = ? AND status NOT LIKE 'CLOSED'", (position_id,)
        ).fetchone())

        if not pos:
            return {"error": "Pozisyon bulunamadı"}

        # Kapatılacak miktar
        close_size   = pos["position_size"] * close_pct
        close_margin = pos["margin_used"]   * close_pct

        # PnL hesapla
        if pos["direction"] == "LONG":
            gross_pnl = (close_price - pos["entry_price"]) * close_size * pos["leverage"]
        else:
            gross_pnl = (pos["entry_price"] - close_price) * close_size * pos["leverage"]

        fees    = close_price * close_size * 0.0005  # %0.05 komisyon
        net_pnl = gross_pnl - fees

        # Kalan pozisyonu güncelle
        new_size   = pos["position_size"] - close_size
        new_margin = pos["margin_used"]   - close_margin

        conn.execute("""
        UPDATE positions
        SET position_size = ?,
            margin_used   = ?
        WHERE id = ?
        """, (new_size, new_margin, position_id))

        # Kullanıcı bakiyesine kısmi karı + marjini ekle
        conn.execute("""
        UPDATE users
        SET balance   = balance + ? + ?,
            total_pnl = total_pnl + ?
        WHERE id = ?
        """, (close_margin, net_pnl, net_pnl, pos["user_id"]))

        roi_pct = (net_pnl / close_margin * 100) if close_margin > 0 else 0

        # Trade history'ye kaydet
        conn.execute("""
        INSERT INTO trade_history
            (user_id, position_id, pair, direction, entry_price, exit_price,
             position_size, margin_used, leverage, gross_pnl, fees, net_pnl,
             roi_pct, close_reason, signal_source, opened_at, duration_mins)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pos["user_id"], position_id, pos["pair"], pos["direction"],
              pos["entry_price"], close_price, close_size,
              close_margin, pos["leverage"], gross_pnl, fees, net_pnl,
              round(roi_pct, 2), reason,
              _get_signal_source(conn, pos),
              pos.get("opened_at"), 0))

    return {"net_pnl": net_pnl, "roi_pct": roi_pct, "close_size": close_size, "close_margin": close_margin}


def update_stop_loss(position_id: int, new_sl: float) -> bool:
    """Pozisyonun stop loss seviyesini günceller."""
    with get_db() as conn:
        conn.execute(
            "UPDATE positions SET stop_loss = ? WHERE id = ?",
            (new_sl, position_id)
        )
    return True


def mark_tp_hit(position_id: int, tp_level: int):
    """TP seviyesinin ulaşıldığını işaretler."""
    with get_db() as conn:
        conn.execute(
            f"UPDATE positions SET tp{tp_level}_hit = 1, status = 'TP{tp_level}_HIT' WHERE id = ?",
            (position_id,)
        )


# ═══════════════════════════════════════════════
#  SİNYAL FONKSİYONLARI
# ═══════════════════════════════════════════════

def save_signal(signal_type: str, pair: str, direction: str, entry_min: float,
                entry_max: float, stop_loss: float, tp1: float, tp2: float = None,
                tp3: float = None, confidence: float = 85.0, timeframe: str = "1h",
                indicators: dict = None, analysis_text: str = None,
                rr_ratio: float = None, expires_in_hours: int = 8) -> int:
    """Yeni sinyal kaydeder."""
    from datetime import timedelta
    valid_until = (datetime.utcnow() + timedelta(hours=expires_in_hours)).isoformat()

    with get_db() as conn:
        cursor = conn.execute("""
        INSERT INTO signals
            (signal_type, pair, direction, entry_min, entry_max, stop_loss,
             tp1, tp2, tp3, confidence, timeframe, indicators, analysis_text,
             rr_ratio, valid_until, expires_in_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (signal_type, pair, direction, entry_min, entry_max, stop_loss,
              tp1, tp2, tp3, confidence, timeframe,
              json.dumps(indicators, cls=_NumpyEncoder) if indicators else None,
              analysis_text, rr_ratio, valid_until, expires_in_hours))
        return cursor.lastrowid


def is_recent_signal_exists(pair: str, direction: str, hours: int = 2) -> bool:
    """Aynı parite ve yönde yakın zamanda sinyal üretilmiş mi kontrol eder."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT COUNT(*) FROM signals
            WHERE pair = ? AND direction = ? 
            AND created_at >= datetime('now', ?)
        """, (pair, direction, f"-{hours} hours")).fetchone()
        return row[0] > 0


def get_recent_signals(signal_type: str = None, limit: int = 50) -> list:
    """Son sinyalleri getirir."""
    with get_db() as conn:
        if signal_type:
            rows = conn.execute("""
            SELECT * FROM signals
            WHERE signal_type = ?
            ORDER BY created_at DESC LIMIT ?
            """, (signal_type, limit)).fetchall()
        else:
            rows = conn.execute("""
            SELECT * FROM signals
            ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def update_signal_status(signal_id: int, status: str, result_pnl: float = None):
    """Sinyal durumunu günceller."""
    with get_db() as conn:
        conn.execute("""
        UPDATE signals
        SET status = ?, result_pnl = ?,
            closed_at = CASE WHEN ? IN ('TP1','TP2','TP3','SL','EXPIRED')
                        THEN datetime('now') ELSE closed_at END
        WHERE id = ?
        """, (status, result_pnl, status, signal_id))


# ═══════════════════════════════════════════════
#  İSTATİSTİK FONKSİYONLARI
# ═══════════════════════════════════════════════

def get_user_stats(user_id: int, days: int = 30) -> dict:
    """Kullanıcının istatistiklerini hesaplar."""
    with get_db() as conn:
        row = conn.execute("""
        SELECT
            COUNT(*)                                    AS total_trades,
            COALESCE(SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END), 0) AS winning_trades,
            COALESCE(SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END), 0) AS losing_trades,
            COALESCE(SUM(net_pnl), 0)                                AS total_pnl,
            COALESCE(AVG(CASE WHEN net_pnl > 0 THEN net_pnl END), 0) AS avg_win,
            COALESCE(AVG(CASE WHEN net_pnl < 0 THEN net_pnl END), 0) AS avg_loss,
            COALESCE(MAX(net_pnl), 0)                                AS best_trade,
            COALESCE(MIN(net_pnl), 0)                                AS worst_trade,
            COALESCE(AVG(duration_mins), 0)                          AS avg_duration,
            COALESCE(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END), 0) AS gross_profit,
            COALESCE(SUM(CASE WHEN net_pnl < 0 THEN net_pnl ELSE 0 END), 0) AS gross_loss
        FROM trade_history
        WHERE user_id = ?
          AND closed_at >= datetime('now', ? || ' days')
        """, (user_id, f"-{days}")).fetchone()

        stats = dict(row) if row else {}
        total = stats.get("total_trades") or 0
        wins  = stats.get("winning_trades") or 0
        stats["win_rate"] = round((wins / total * 100), 1) if total > 0 else 0.0
        return stats


def get_trade_history(user_id: int, limit: int = 20, pair: str = None) -> list:
    """Kullanıcının işlem geçmişini getirir."""
    with get_db() as conn:
        if pair:
            rows = conn.execute("""
            SELECT * FROM trade_history
            WHERE user_id = ? AND pair = ?
            ORDER BY closed_at DESC LIMIT ?
            """, (user_id, pair, limit)).fetchall()
        else:
            rows = conn.execute("""
            SELECT * FROM trade_history
            WHERE user_id = ?
            ORDER BY closed_at DESC LIMIT ?
            """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def reset_user_data(user_id: int):
    """Kullanıcının tüm verilerini sıfırlar (ayarlar korunur)."""
    with get_db() as conn:
        conn.execute("DELETE FROM trade_history WHERE user_id = ?", (user_id,))
        conn.execute(
            "UPDATE positions SET status='CLOSED', close_reason='RESET' WHERE user_id = ? AND status='ACTIVE'",
            (user_id,)
        )
        conn.execute("""
        UPDATE users
        SET balance   = ?,
            total_pnl = 0.0
        WHERE id = ?
        """, (INITIAL_BALANCE, user_id))
        conn.execute("DELETE FROM ai_coach_notes WHERE user_id = ?", (user_id,))
    logger.info(f"Kullanıcı {user_id} verisi sıfırlandı.")


if __name__ == "__main__":
    init_database()
    print("Veritabanı başarıyla oluşturuldu!")

# ═══════════════════════════════════════════════
#  FİYAT ALARMI FONKSİYONLARI
# ═══════════════════════════════════════════════

def create_price_alarm(user_id: int, signal_id: int, pair: str,
                       direction: str, entry_min: float, entry_max: float) -> int:
    """Yeni fiyat alarmı oluşturur."""
    with get_db() as conn:
        # Aynı coin için aktif alarm varsa iptal et
        conn.execute(
            "UPDATE price_alarms SET status='CANCELLED' WHERE user_id=? AND pair=? AND status='ACTIVE'",
            (user_id, pair)
        )
        cursor = conn.execute("""
        INSERT INTO price_alarms (user_id, signal_id, pair, direction, entry_min, entry_max)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, signal_id, pair, direction, entry_min, entry_max))
        return cursor.lastrowid

def get_active_alarms() -> list:
    """Tüm aktif alarmları döner."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM price_alarms WHERE status='ACTIVE'"
        ).fetchall()
        return [dict(r) for r in rows]

def trigger_alarm(alarm_id: int) -> bool:
    """Alarmı tetiklenmiş olarak işaretler."""
    with get_db() as conn:
        conn.execute("""
        UPDATE price_alarms
        SET status='TRIGGERED', triggered_at=datetime('now')
        WHERE id=?
        """, (alarm_id,))
    return True

def cancel_alarm(user_id: int, pair: str) -> bool:
    """Kullanıcının belirtilen coin alarmını iptal eder."""
    with get_db() as conn:
        conn.execute(
            "UPDATE price_alarms SET status='CANCELLED' WHERE user_id=? AND pair=? AND status='ACTIVE'",
            (user_id, pair)
        )
    return True
