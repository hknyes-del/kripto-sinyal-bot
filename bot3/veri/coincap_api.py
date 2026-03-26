import aiohttp
import pandas as pd
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

class CoinCapAPI:
    """CoinCap - Her yerde açık!"""
    
    def __init__(self):
        self.base_url = "https://api.coincap.io/v2"
        self.veri_havuzu = {}
        self.son_guncelleme = {}
        self.session = None
        logger.info("✅ CoinCap API başlatıldı")
    
    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def veri_cek_rest(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        try:
            # CoinCap ID map
            coin_map = {
                'BTC/USDT': 'bitcoin',
                'ETH/USDT': 'ethereum',
                'BNB/USDT': 'binance-coin',
                'SOL/USDT': 'solana',
                'XRP/USDT': 'xrp',
                'ADA/USDT': 'cardano',
            }
            
            coin_id = coin_map.get(symbol)
            if not coin_id:
                return pd.DataFrame()
            
            interval = 'h1' if timeframe == '1h' else 'h4' if timeframe == '4h' else 'd1'
            
            url = f"{self.base_url}/assets/{coin_id}/history"
            params = {
                'interval': interval,
                'limit': limit
            }
            
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if 'data' not in data:
                    return pd.DataFrame()
                
                df = pd.DataFrame(data['data'])
                df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
                df.set_index('timestamp', inplace=True)
                df = df.astype(float)
                
                return df
                
        except Exception as e:
            logger.error(f"❌ CoinCap hatası: {e}")
            return pd.DataFrame()

coincap = CoinCapAPI()