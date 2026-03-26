import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
import json
import websockets
from typing import Dict, List, Optional, Tuple
import logging
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VeriToplayici:
    """
    Çoklu zaman diliminde, 150+ varlık için optimize edilmiş veri toplayıcı
    WebSocket + REST hybrid mimari
    """
    
    def __init__(self):
        """Veri toplayıcıyı başlat"""
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'rateLimit': 1200,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'recvWindow': 5000
            }
        })
        
        # Veri havuzu: {(sembol, timeframe): DataFrame}
        self.veri_havuzu = {}
        
        # Son güncelleme zamanları
        self.son_guncelleme = {}
        
        # WebSocket bağlantıları
        self.websocket_baglantilari = {}
        
        # WebSocket çalışma durumu
        self.websocket_calisiyor = False
        
        logger.info("✅ VeriToplayici başlatıldı")
    
    async def veri_cek_rest(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """
        REST API ile geçmiş veri çekme
        
        Args:
            symbol: Sembol (örn: 'BTC/USDT')
            timeframe: Zaman dilimi (örn: '1d', '4h', '1h', '15m', '5m')
            limit: Mum sayısı (varsayılan: 500)
        
        Returns:
            pd.DataFrame: OHLCV verileri
        """
        try:
            # Timeframe dönüşümü
            tf_map = {
                '1d': '1d',
                '4h': '4h',
                '1h': '1h',
                '15m': '15m',
                '5m': '5m',
                '1m': '1m'
            }
            
            tf = tf_map.get(timeframe, timeframe)
            
            # Veriyi çek
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol, 
                tf, 
                limit=limit
            )
            
            if not ohlcv:
                logger.warning(f"⚠️ {symbol} {tf} veri çekilemedi")
                return pd.DataFrame()
            
            # DataFrame oluştur
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Timestamp'i datetime'a çevir
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Veri temizliği
            df = df.astype({
                'open': 'float64',
                'high': 'float64',
                'low': 'float64',
                'close': 'float64',
                'volume': 'float64'
            })
            
            # Teknik göstergeleri ekle
            df = self._teknik_gostergeler_ekle(df)
            
            logger.info(f"✅ {symbol} {timeframe} veri çekildi: {len(df)} mum")
            return df
            
        except ccxt.RateLimitExceeded:
            logger.warning(f"⚠️ Rate limit aşıldı {symbol} {timeframe}, 5 saniye bekleniyor...")
            await asyncio.sleep(5)
            return await self.veri_cek_rest(symbol, timeframe, limit)
            
        except ccxt.NetworkError as e:
            logger.error(f"🌐 Network hatası {symbol} {timeframe}: {e}")
            await asyncio.sleep(2)
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Veri çekme hatası {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def _teknik_gostergeler_ekle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Teknik analiz göstergelerini ekle
        """
        if df.empty:
            return df
        
        try:
            # Hareketli ortalamalar
            df['sma_20'] = df['close'].rolling(window=20, min_periods=1).mean()
            df['sma_50'] = df['close'].rolling(window=50, min_periods=1).mean()
            df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
            
            # Hacim ortalaması
            df['volume_sma'] = df['volume'].rolling(window=20, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            df['volume_ratio'] = df['volume_ratio'].replace([np.inf, -np.inf], 1).fillna(1)
            
            # Mum karakteristikleri
            df['range'] = df['high'] - df['low']
            df['body'] = abs(df['close'] - df['open'])
            df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
            df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
            
            # Wick oranları
            df['upper_wick_ratio'] = df['upper_wick'] / df['range']
            df['lower_wick_ratio'] = df['lower_wick'] / df['range']
            df['body_ratio'] = df['body'] / df['range']
            
            # Sonsuz ve NaN değerleri temizle
            for col in ['upper_wick_ratio', 'lower_wick_ratio', 'body_ratio']:
                df[col] = df[col].replace([np.inf, -np.inf], 0).fillna(0)
            
            # Momentum
            df['roc'] = df['close'].pct_change(periods=10) * 100
            df['roc'] = df['roc'].fillna(0)
            
            # Volatilite
            df['volatility'] = df['range'] / df['close'] * 100
            df['volatility'] = df['volatility'].fillna(0)
            
        except Exception as e:
            logger.error(f"Teknik gösterge ekleme hatası: {e}")
        
        return df
    
    async def tum_verileri_guncelle(self, semboller: List[str] = None, limit: int = 200):
        """
        Tüm semboller ve zaman dilimleri için veri güncelleme
        
        Args:
            semboller: Güncellenecek semboller (None = config'deki tüm semboller)
            limit: Her sembol için çekilecek mum sayısı
        """
        if semboller is None:
            semboller = config.TARGET_SYMBOLS
        
        # Zaman dilimleri
        zaman_dilimleri = ['1d', '4h', '1h', '15m', '5m']
        
        # Paralel veri çekme için task listesi
        tasks = []
        task_info = []
        
        for sembol in semboller:
            for tf in zaman_dilimleri:
                task = self.veri_cek_rest(sembol, tf, limit)
                tasks.append(task)
                task_info.append((sembol, tf))
        
        # Tüm task'ları paralel çalıştır
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sonuçları veri havuzuna ekle
        for (sembol, tf), df in zip(task_info, results):
            if isinstance(df, Exception):
                logger.error(f"❌ {sembol} {tf} güncellenemedi: {df}")
                continue
                
            if not df.empty:
                self.veri_havuzu[(sembol, tf)] = df
                self.son_guncelleme[(sembol, tf)] = datetime.now()
        
        logger.info(f"🔄 Veri havuzu güncellendi: {len(self.veri_havuzu)} tablo")
        return self.veri_havuzu
    
    def veri_al(self, sembol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Veri havuzundan veri al
        
        Args:
            sembol: Sembol (örn: 'BTC/USDT')
            timeframe: Zaman dilimi (örn: '1d', '4h', '1h', '15m', '5m')
        
        Returns:
            pd.DataFrame: Veri veya None
        """
        anahtar = (sembol, timeframe)
        return self.veri_havuzu.get(anahtar, None)
    
    async def kapat(self):
        """Tüm bağlantıları kapat ve kaynakları temizle"""
        logger.info("🛑 Veri toplayıcı kapatılıyor...")
        
        try:
            await self.exchange.close()
            logger.info("✅ Binance bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"❌ Binance kapatma hatası: {e}")
        
        self.veri_havuzu.clear()
        self.son_guncelleme.clear()
        
        logger.info("✅ Veri toplayıcı kapatıldı")

# Global veri toplayıcı instance
veri_topla = VeriToplayici()