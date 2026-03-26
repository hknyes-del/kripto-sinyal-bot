"""
╔══════════════════════════════════════════════════════════════╗
║         DOSYA 1: config.py — Tüm Ayarlar ve Sabitler        ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Bot'un tüm yapılandırma ayarlarını, sabitlerini ve
çevresel değişkenlerini merkezi olarak yönetir.
"""

import os
import pytz
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  TELEGRAM BOT AYARLARI
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_USER_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# ─────────────────────────────────────────────
#  BINANCE API AYARLARI (Sadece okuma izni!)
# ─────────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_BASE_URL = "https://api.binance.com"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# ─────────────────────────────────────────────
#  ZAMAN DİLİMİ
# ─────────────────────────────────────────────
TIMEZONE = pytz.timezone("Europe/Istanbul")  # GMT+3 Türkiye saati
TIMEZONE_LABEL = "GMT+3 (Türkiye)"

# ─────────────────────────────────────────────
#  DEMO HESAP AYARLARI
# ─────────────────────────────────────────────
INITIAL_BALANCE = 10_000.00  # Başlangıç bakiyesi ($)
DEFAULT_MARGIN = 20.00  # Varsayılan işlem marjini ($)
MIN_MARGIN = 5.00  # Minimum marjin ($)
MAX_MARGIN = 1_000.00  # Maksimum marjin ($)
MARGIN_CALL_LEVEL = 120.0  # Marjin çağrısı eşiği (%)
LIQUIDATION_LEVEL = 100.0  # Otomatik tasfiye eşiği (%)

# ─────────────────────────────────────────────
#  KALDIRAÇ SEÇENEKLERİ
# ─────────────────────────────────────────────
LEVERAGE_OPTIONS = [1, 2, 3, 5, 10, 20, 50, 100]
DEFAULT_LEVERAGE = 5

# ─────────────────────────────────────────────
#  ZAMAN DİLİMLERİ (GRAFIKLER İÇİN)
# ─────────────────────────────────────────────
TIMEFRAMES = {
    "1m": {"label": "1 Dakika", "seconds": 60},
    "5m": {"label": "5 Dakika", "seconds": 300},
    "15m": {"label": "15 Dakika", "seconds": 900},
    "1h": {"label": "1 Saat", "seconds": 3600},
    "4h": {"label": "4 Saat", "seconds": 14400},
    "1d": {"label": "1 Gün", "seconds": 86400},
    "1w": {"label": "1 Hafta", "seconds": 604800},
}
DEFAULT_TIMEFRAME = "1h"

# ─────────────────────────────────────────────
#  DESTEKLENEN KRİPTO ÇİFTLERİ
# ─────────────────────────────────────────────
SUPPORTED_PAIRS = [
    # Stablecoin YOK (USDC, FDUSD, PAXG, USD1, BUSD, TUSD vb. hariç)
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "LTCUSDT",
    "UNIUSDT",
    "DOTUSDT",
    "NEARUSDT",
    "ARBUSDT",
    "AAVEUSDT",
    "TRXUSDT",
    "BCHUSDT",
    "SUIUSDT",
    "TAOUSDT",
    "ENAUSDT",
    "WLDUSDT",
    "INJUSDT",
    "SEIUSDT",
    "APTUSDT",
    "OPUSDT",
    "FILUSDT",
    "ZECUSDT",
    "PEPEUSDT",
    "BONKUSDT",
    "SHIBUSDT",
    "TRUMPUSDT",
    "VIRTUALUSDT",
    "RENDERUSDT",
    "FETUSDT",
    "PENDLEUSDT",
    "ATOMUSDT",
    "XLMUSDT",
    "HBARUSDT",
    "ICPUSDT",
    "TONUSDT",
    "ONDOUSDT",
    "CAKEUSDT",
    "CRVUSDT",
    "SNXUSDT",
    "ETCUSDT",
    "WIFUSDT",
    "POLUSDT",
    "DASHUSDT",
    "CHZUSDT",
    "VETUSDT",
    "ARUSDT",
    "ROSEUSDT",
    "STRKUSDT",
    "ZKUSDT",
    "WBTCUSDT",
]

# Stablecoin listesi — sinyal üretiminde bu coinler filtrelenir
STABLECOIN_BLACKLIST = {
    "USDCUSDT",
    "FDUSDUSDT",
    "PAXGUSDT",
    "USD1USDT",
    "BUSDUSDT",
    "TUSDUSDT",
    "USDPUSDT",
    "DAIUSDT",
    "USDEUSDT",
    "RLUSDUSDT",
    "EULUSDT",
    "XUSDUSDT",
    "BFUSDUSDT",
    "EURUSDT",
}
DEFAULT_PAIR = "BTCUSDT"

# ─────────────────────────────────────────────
#  SİNYAL AYARLARI
# ─────────────────────────────────────────────
MIN_SIGNAL_CONFIDENCE = 75  # Minimum güven skoru (%)
SIGNAL_VALIDITY_HOURS = {  # Sinyal geçerlilik süreleri
    "SCALP": 2,
    "DAY": 8,
    "SWING": 48,
}
MAX_BACKTEST_SIGNALS = 50  # Backtest için max sinyal sayısı
TP_PARTIAL_CLOSE = {  # Her TP'de kapatılacak yüzdeler
    "TP1": 30,
    "TP2": 40,
    "TP3": 30,
}

# ─────────────────────────────────────────────
#  TEKNİK ANALİZ PARAMETRELERİ
# ─────────────────────────────────────────────
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
EMA_SHORT = 20
EMA_MEDIUM = 50
EMA_LONG = 200
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
ATR_PERIOD = 14

# ─────────────────────────────────────────────
#  RİSK YÖNETİMİ
# ─────────────────────────────────────────────
MAX_RISK_PER_TRADE = 2.0  # Hesabın maksimum %2'si risk
DAILY_LOSS_LIMIT_PCT = 5.0  # Günlük maksimum kayıp (%)
MAX_OPEN_POSITIONS = 10  # Maksimum açık pozisyon sayısı

# ─────────────────────────────────────────────
#  VERİTABANI
# ─────────────────────────────────────────────
DATABASE_PATH = "crypto_bot.db"

# ─────────────────────────────────────────────
#  EMOJİ SABITLERI (UI tutarlılığı için)
# ─────────────────────────────────────────────
EMOJI = {
    "bull": "📈",
    "bear": "📉",
    "profit": "💰",
    "loss": "🔴",
    "warning": "⚠️",
    "success": "✅",
    "fail": "❌",
    "signal": "🚀",
    "chart": "📊",
    "settings": "⚙️",
    "coach": "🤖",
    "fire": "🔥",
    "clock": "🕐",
    "dollar": "💵",
    "target": "🎯",
    "stop": "🛑",
    "bell": "🔔",
    "star": "⭐",
    "lock": "🔐",
    "info": "ℹ️",
    "back": "◀️",
    "next": "▶️",
    "refresh": "🔄",
    "trophy": "🏆",
    "lightning": "⚡",
}

# ─────────────────────────────────────────────
#  RENK TEMALARI (Mesaj formatı için)
# ─────────────────────────────────────────────
SIGNAL_TYPES = {
    "LONG": {"emoji": "📈", "label": "LONG  (Alış)"},
    "SHORT": {"emoji": "📉", "label": "SHORT (Satış)"},
}

STATUS_LABELS = {
    "PENDING": "⏳ Beklemede",
    "ACTIVE": "🟢 Aktif",
    "TP1_HIT": "🎯 TP1 Ulaşıldı",
    "TP2_HIT": "🎯🎯 TP2 Ulaşıldı",
    "TP3_HIT": "🏆 TP3 Ulaşıldı",
    "SL_HIT": "🛑 SL Tetiklendi",
    "CLOSED": "⚫ Kapatıldı",
    "EXPIRED": "⏰ Süresi Doldu",
}

# ─────────────────────────────────────────────
#  ZAMANLAYICI AYARLARI (APScheduler)
# ─────────────────────────────────────────────
PRICE_CHECK_INTERVAL = 30  # Fiyat kontrolü (saniye)
SIGNAL_GEN_INTERVAL = 120  # Sinyal üretimi (saniye = 2 dk)
DAILY_REPORT_HOUR = 8  # Günlük rapor saati (08:00 GMT+3)
WEEKLY_REPORT_WEEKDAY = 6  # Haftalık rapor günü (0=Pzt, 6=Paz)

print("✅ Config yüklendi.")
