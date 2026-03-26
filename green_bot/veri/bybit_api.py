import aiohttp
import asyncio
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BybitAPI:
    """Doğrudan Bybit API bağlantısı - CCXT'siz!"""
    
    def __init__(self):
        self.base_url = "https://api.bybit.com"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        await self.session.close()
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200):
        """Bybit'ten OHLCV verisi çek"""
        
        # Sembol formatı: BTCUSDT
        symbol_bybit = symbol.replace('/', '')
        
        # Timeframe dönüşümü
        tf_map = {
            '1d': 'D',
            '4h': '240',
            '1h': '60',
            '15m': '15',
            '5m': '5',
            '1m': '1'
        }
        tf = tf_map.get(timeframe, '60')
        
        url = f"{self.base_url}/v5/market/kline"
        params = {
            'category': 'spot',
            'symbol': symbol_bybit,
            'interval': tf,
            'limit': limit
        }
        
        async with self.session.get(url, params=params) as response:
            data = await response.json()
            
            if data['retCode'] == 0:
                df = pd.DataFrame(data['result']['list'], 
                                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
                df.set_index('timestamp', inplace=True)
                df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
                return df
            else:
                logger.error(f"Bybit hatası: {data['retMsg']}")
                return None

# Global instance
bybit_api = BybitAPI()