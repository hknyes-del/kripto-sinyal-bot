import os
from dataclasses import dataclass, field
from typing import List, Dict
from dotenv import load_dotenv

# Ana klasördeki .env'yi yükle
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

@dataclass
class Config:
    # TELEGRAM
    TELEGRAM_BOT_TOKEN: str = os.getenv("BOT3_TOKEN", "YOUR_BOT_TOKEN_HERE")
    TELEGRAM_CHAT_ID: str = os.getenv("BOT3_CHAT_ID", "782795529")
    
    # 🚀 75 POPÜLER COİN - AKTİF!
    TARGET_SYMBOLS: List[str] = field(default_factory=lambda: [
        # TOP 10
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
        'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'TRX/USDT',
        
        # LAYER 1
        'MATIC/USDT', 'FTM/USDT', 'NEAR/USDT', 'ALGO/USDT', 'ICP/USDT',
        'FIL/USDT', 'VET/USDT', 'HBAR/USDT', 'EGLD/USDT', 'THETA/USDT',
        
        # LAYER 2
        'ARB/USDT', 'OP/USDT', 'METIS/USDT', 'IMX/USDT', 'SKL/USDT',
        'LRC/USDT', 'CTSI/USDT', 'ZIL/USDT', 'CELO/USDT', 'BOBA/USDT',
        
        # DEFI
        'UNI/USDT', 'AAVE/USDT', 'MKR/USDT', 'SNX/USDT', 'COMP/USDT',
        'LDO/USDT', 'FXS/USDT', 'CRV/USDT', 'SUSHI/USDT', 'DYDX/USDT',
        
        # GAME - NFT
        'SAND/USDT', 'MANA/USDT', 'AXS/USDT', 'GALA/USDT', 'ENJ/USDT',
        'APE/USDT', 'ALICE/USDT', 'ILV/USDT', 'TLM/USDT', 'CHZ/USDT',
        
        # ORACLE
        'LINK/USDT', 'BAND/USDT', 'GRT/USDT', 'API3/USDT', 'TRB/USDT',
        
        # MEME
        'SHIB/USDT', 'FLOKI/USDT', 'PEPE/USDT', 'BONK/USDT', 'WIF/USDT',
        
        # CEX
        'LEO/USDT', 'OKB/USDT', 'CRO/USDT', 'KCS/USDT', 'BGB/USDT',
        
        # YENİ NESİL
        'SUI/USDT', 'APT/USDT', 'SEI/USDT', 'TIA/USDT', 'INJ/USDT',
        
        # POPÜLER
        'RNDR/USDT', 'STX/USDT', 'QNT/USDT', 'FLOW/USDT', 'ROSE/USDT'
    ])
    
    # ZAMAN DİLİMLERİ
    TIMEFRAMES: Dict[str, str] = field(default_factory=lambda: {
        '1D': '1d',
        '4H': '4h', 
        '1H': '1h',
        '15M': '15m',
        '5M': '5m'
    })

config = Config()