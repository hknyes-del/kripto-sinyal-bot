import os
from dataclasses import dataclass, field
from typing import List, Dict
from dotenv import load_dotenv

# Ana klasördeki .env'yi yükle
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

@dataclass
class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("GREEN_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    TELEGRAM_CHAT_ID: str = os.getenv("GREEN_CHAT_ID", "782795529")
    
    # 🔥 BERKAY HIGH LIQUIDITY + VOLATIL SEÇİMLER
    TARGET_SYMBOLS: List[str] = field(default_factory=lambda: [
        # 🥇 TOP 20 (YÜKSEK LİKİDİTE - %90+ hacim)
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
        'DOGE/USDT', 'ADA/USDT', 'TRX/USDT', 'AVAX/USDT', 'LINK/USDT',
        'MATIC/USDT', 'DOT/USDT', 'LTC/USDT', 'BCH/USDT', 'UNI/USDT',
        
        # 🔥 BERKAY FAVORİLER (Volatil + Likidite)
        'AAVE/USDT', 'MKR/USDT', 'SUI/USDT', 'APT/USDT', 'INJ/USDT',
        'NEAR/USDT', 'ATOM/USDT', 'FIL/USDT', 'ICP/USDT', 'ARB/USDT',
        
        # 📈 L2 + Yeni Nesil (Haftalık %5+ move)
        'OP/USDT', 'IMX/USDT', 'STX/USDT', 'SEI/USDT', 'TIA/USDT',
        'RNDR/USDT', 'QNT/USDT', 'FLOW/USDT', 'ROSE/USDT',
        
        # ⚡ Meme (Yüksek volatilite - dikkatli)
        'SHIB/USDT', 'PEPE/USDT', 'WIF/USDT', 'FLOKI/USDT',
        
        # 💎 DeFi + Oracle (Berkay confluence)
        'SNX/USDT', 'CRV/USDT', 'GRT/USDT', 'BAND/USDT'
    ])
    
    # 🎯 BERKAY FİLTRE EŞİKLERİ
    MIN_VOLUME_24H: float = 100_000_000  # $100M+ hacim
    MIN_PRICE: float = 0.0001  # Düşük coin yok
    MAX_PRICE: float = 100_000  # BTC max
    
    # 📊 SNIPER EŞİKLERİ
    BERKAY_SKOR_ESIK: int = 85  # %85+ sinyal
    SUPER_MODEL_ESIK: int = 90  # A+++ sadece
    
    # ⏱️ TARAMA AYARLARI
    TARAMA_SURESI: int = 300  # 5dk interval
    BATCH_SIZE: int = 8       # Paralel tarama
    
    TIMEFRAMES: Dict[str, str] = field(default_factory=lambda: {
        '1W': '1w', '1D': '1d', '4H': '4h', '1H': '1h', '15M': '15m', '5M': '5m'
    })
    
    # 🔗 KUZEN PARİTELER (SMT)
    KUZEN_PARİTELER: Dict[str, str] = field(default_factory=lambda: {
        'BTC/USDT': 'ETH/USDT', 'ETH/USDT': 'BTC/USDT',
        'SOL/USDT': 'AVAX/USDT', 'BNB/USDT': 'TRX/USDT'
    })

config = Config()
