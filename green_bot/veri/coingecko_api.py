import aiohttp
import pandas as pd
from datetime import datetime
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoinGeckoAPI:
    """CoinGecko - DÜNYANIN HER YERİNDE AÇIK!"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.veri_havuzu = {}
        self.son_guncelleme = {}
        self.session = None
        logger.info("✅ CoinGecko API başlatıldı")
    
    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def veri_cek_rest(self, symbol: str, timeframe: str, limit: int = 50) -> pd.DataFrame:
        """CoinGecko'dan OHLCV verisi çek"""
        try:
            # CoinGecko ID map (EN POPÜLER 10 COIN)
            coin_map = {
                'BTC/USDT': 'bitcoin',
                'ETH/USDT': 'ethereum',
                'BNB/USDT': 'binancecoin',
                'SOL/USDT': 'solana',
                'XRP/USDT': 'ripple',
                'ADA/USDT': 'cardano',
                'DOGE/USDT': 'dogecoin',
                'DOT/USDT': 'polkadot',
                'LINK/USDT': 'chainlink',
                'MATIC/USDT': 'matic-network',
                'AVAX/USDT': 'avalanche-2',
                'UNI/USDT': 'uniswap',
                'ATOM/USDT': 'cosmos',
                'ETC/USDT': 'ethereum-classic',
                'FIL/USDT': 'filecoin',
            }
            
            coin_id = coin_map.get(symbol)
            if not coin_id:
                logger.warning(f"⚠️ {symbol} CoinGecko'da yok")
                return pd.DataFrame()
            
            # Timeframe dönüşümü (CoinGecko gün bazında çalışır)
            days_map = {
                '1h': 1,
                '4h': 2,
                '1d': 30,
                '15m': 1,
                '5m': 1
            }
            days = days_map.get(timeframe, 1)
            
            url = f"{self.base_url}/coins/{coin_id}/ohlc"
            params = {
                'vs_currency': 'usd',
                'days': days
            }
            
            logger.info(f"🔍 {symbol} {timeframe} CoinGecko'dan çekiliyor...")
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ CoinGecko HTTP {response.status}")
                    return pd.DataFrame()
                
                data = await response.json()
                
                if not data:
                    return pd.DataFrame()
                
                # DataFrame oluştur
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # Volume yok (CoinGecko vermiyor), varsayılan ekle
                df['volume'] = 1000000  # Sabit hacim
                
                logger.info(f"✅ {symbol} {timeframe} CoinGecko'dan çekildi: {len(df)} mum")
                return df
                
        except Exception as e:
            logger.error(f"❌ CoinGecko hatası {symbol}: {e}")
            return pd.DataFrame()
    
    async def kapat(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("✅ CoinGecko bağlantısı kapatıldı")

# Global instance
coingecko_api = CoinGeckoAPI()