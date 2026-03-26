import os
from dotenv import load_dotenv

# Ana klasördeki .env'yi yükle
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

"""
Ayarlar dosyası
Burada API anahtarları ve temel ayarlar var
"""

# Binance API (Testnet kullan başta)
BINANCE_API_KEY = "pjXPnYowZ158RWaRiXcYuE8dr8KjpYRm1KmfnWFA6GtxHlVcnisravhAVRQofoih"
BINANCE_API_SECRET = "uFwSv9umK04lPduyiOA4dZjW7AzbDFaqHQbwzxPqbvvQZ3T1YLBC3wCKygMIVV50"
USE_TESTNET = True  # Başta testnet kullan

# Telegram Bildirim
TELEGRAM_TOKEN = os.getenv("BOT4_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("BOT4_CHAT_ID", "782795529")

# Tarama Ayarları
SCAN_INTERVAL_MINUTES = 5  # Her 5 dakikada tara
TOTAL_COINS_TO_SCAN = 100  # İlk 100 coin
MIN_CONFLUENCE_SCORE = 6   # Minimum A+ sinyal

# Timeframe'ler
TIMEFRAMES = {
    'HTF': '4h',      # High Timeframe - Bias için
    'MTF': '1h',      # Medium Timeframe - Setup için
    'LTF': '15m',     # Low Timeframe - Entry için
    'EXECUTION': '5m' # Execution timeframe
}

# Risk Ayarları
RISK_PER_TRADE_PERCENT = 1.0  # Her işlemde %1 risk
MAX_LEVERAGE = 3              # Maksimum kaldıraç
MIN_RISK_REWARD = 2.0         # Minimum 1:2 R:R

# Kill Zone Saatleri (Türkiye)
KILL_ZONE_START = "15:30"
KILL_ZONE_END = "19:00"