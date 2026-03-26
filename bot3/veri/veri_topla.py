# veri/veri_topla.py
import ccxt
import pandas as pd
import numpy as np
import logging
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VeriToplayici:
    """Çoklu zaman diliminde veri toplayıcı"""
    
    def __init__(self):
        """Veri toplayıcıyı başlat"""
        # ✅ Senkron exchange
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'rateLimit': 1200,
            'timeout': 30000
        })
        
        self.veri_havuzu = {}
        self.son_guncelleme = {}
        logger.info("✅ VeriToplayici başlatıldı")
    
    def veri_cek_rest(self, symbol: str, timeframe: str, limit: int = 500, retry: int = 0) -> pd.DataFrame:
        """REST API ile geçmiş veri çekme"""
        try:
            # Timeframe dönüşümü
            tf_map = {
                '1d': '1d', '4h': '4h', '1h': '1h',
                '15m': '15m', '5m': '5m', '1m': '1m'
            }
            tf = tf_map.get(timeframe, timeframe)
            
            logger.info(f"📊 {symbol} {tf} çekiliyor...")
            
            # ✅ await OLMADAN çağır
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=tf,
                limit=limit
            )
            
            if not ohlcv or len(ohlcv) == 0:
                logger.warning(f"⚠️ {symbol} {tf} veri çekilemedi")
                return pd.DataFrame()
            
            # DataFrame oluştur
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
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
            import time
            time.sleep(5)
            if retry < 3:
                return self.veri_cek_rest(symbol, timeframe, limit, retry + 1)
            return pd.DataFrame()
            
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            logger.warning(f"⚠️ Ağ hatası {symbol} {timeframe}: {str(e)[:50]}")
            
            if retry < 3:
                import time
                wait_time = 5 * (retry + 1)
                logger.info(f"🔄 {wait_time} saniye sonra yeniden deneniyor...")
                time.sleep(wait_time)
                return self.veri_cek_rest(symbol, timeframe, limit, retry + 1)
            
            logger.error(f"❌ {symbol} {timeframe} 3 deneme sonrası başarısız")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"❌ Veri çekme hatası {symbol} {timeframe}: {str(e)[:100]}")
            return pd.DataFrame()
    
    def _teknik_gostergeler_ekle(self, df: pd.DataFrame) -> pd.DataFrame:
        """Teknik analiz göstergelerini ekle"""
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
    
    def tum_verileri_guncelle(self, semboller: list = None, limit: int = 200):
        """Tüm semboller ve zaman dilimleri için veri güncelleme"""
        if semboller is None:
            semboller = config.TARGET_SYMBOLS
        
        zaman_dilimleri = ['1d', '4h', '1h', '15m', '5m']
        
        basarili = 0
        basarisiz = 0
        
        for sembol in semboller:
            for tf in zaman_dilimleri:
                df = self.veri_cek_rest(sembol, tf, limit)
                
                if not df.empty:
                    self.veri_havuzu[(sembol, tf)] = df
                    basarili += 1
                else:
                    basarisiz += 1
        
        logger.info(f"🔄 Veri havuzu güncellendi: ✅ {basarili} / ❌ {basarisiz}")
        return self.veri_havuzu
    
    def veri_al(self, sembol: str, timeframe: str) -> pd.DataFrame:
        """Veri havuzundan veri al"""
        anahtar = (sembol, timeframe)
        return self.veri_havuzu.get(anahtar, pd.DataFrame())
    
    def kapat(self):
        """Tüm bağlantıları kapat"""
        logger.info("🛑 Veri toplayıcı kapatılıyor...")
        try:
            self.exchange.close()
            logger.info("✅ Binance bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"❌ Binance kapatma hatası: {e}")
        
        self.veri_havuzu.clear()
        logger.info("✅ Veri toplayıcı kapatıldı")

# Global instance
veri_topla = VeriToplayici()
