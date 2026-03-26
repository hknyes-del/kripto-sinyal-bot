"""
Binance veri çekici - v3 (API key gerektirmeyen public endpoint)
OHLCV ve sembol listesi için authentication GEREKMİYOR.
API key sadece order/balance için lazım - buraya geçmiyoruz.
"""

import ccxt
import pandas as pd
import time

# Sabit, doğrulanmış Binance Spot sembolleri (public endpoint'e gerek yok)
# Bu liste Binance spot piyasasındaki gerçek USDT pariteleridir
VALIDATED_COINS = [
    "BTC/USDT",  "ETH/USDT",  "BNB/USDT",  "XRP/USDT",  "SOL/USDT",
    "ADA/USDT",  "DOGE/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT",
    "TRX/USDT",  "LINK/USDT", "POL/USDT",  "LTC/USDT",  "BCH/USDT",
    "UNI/USDT",  "NEAR/USDT", "ATOM/USDT", "XLM/USDT",  "ETC/USDT",
    "APT/USDT",  "FIL/USDT",  "VET/USDT",  "HBAR/USDT", "ALGO/USDT",
    "SAND/USDT", "MANA/USDT", "AXS/USDT",  "EOS/USDT",  "AAVE/USDT",
    "XTZ/USDT",  "CAKE/USDT", "MKR/USDT",  "COMP/USDT", "STX/USDT",
    "GRT/USDT",  "CRV/USDT",  "SNX/USDT",  "1INCH/USDT","CHZ/USDT",
    "ENJ/USDT",  "ZIL/USDT",  "AR/USDT",   "KSM/USDT",  "BAT/USDT",
    "ZEC/USDT",  "NEO/USDT",  "QTUM/USDT", "ZRX/USDT",  "BAL/USDT",
    "SUSHI/USDT","YFI/USDT",  "UMA/USDT",  "LRC/USDT",  "REN/USDT",
    "OCEAN/USDT","BAND/USDT", "KNC/USDT",  "RSR/USDT",  "BNT/USDT",
    "KAVA/USDT", "FET/USDT",  "MASK/USDT", "FLOW/USDT", "OP/USDT",
    "ARB/USDT",  "SUI/USDT",  "SEI/USDT",  "TIA/USDT",  "INJ/USDT",
    "WLD/USDT",  "PEPE/USDT", "FLOKI/USDT","BONK/USDT", "JTO/USDT",
    "PYTH/USDT", "STRK/USDT", "ORDI/USDT", "LUNC/USDT", "GMT/USDT",
    "APE/USDT",  "CKB/USDT",  "ICX/USDT",  "TWT/USDT",  "DENT/USDT",
    "WIN/USDT",  "HOT/USDT",  "NKN/USDT",  "OGN/USDT",  "CTSI/USDT",
    "ALPHA/USDT","BEL/USDT",  "SFP/USDT",  "FTM/USDT",  "EGLD/USDT",
    "ILV/USDT",  "THETA/USDT","WAN/USDT",  "ONT/USDT",  "IOTA/USDT",
]

# SMT için korele çiftler
CORRELATED_PAIRS = {
    "BTC/USDT":  "ETH/USDT",
    "ETH/USDT":  "BTC/USDT",
    "SOL/USDT":  "AVAX/USDT",
    "AVAX/USDT": "SOL/USDT",
    "LINK/USDT": "BAND/USDT",
    "UNI/USDT":  "SUSHI/USDT",
    "ARB/USDT":  "OP/USDT",
    "OP/USDT":   "ARB/USDT",
}


class BinanceDataFetcher:
    def __init__(self):
        # PUBLIC exchange — API key gerektirmez
        # OHLCV ve market info için authentication ŞART DEĞİL
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
            # API key YÜKLEME: sadece order/balance için lazım
            # Burada kulllanmıyoruz
        })

    def fetch_top_coins(self, n=100):
        """
        Doğrulanmış coin listesinden ilk N tanesini döndür
        """
        return VALIDATED_COINS[:n]

    def fetch_ohlcv(self, symbol, timeframe, limit=200):
        """
        OHLCV verisi çek — PUBLIC endpoint, key gerekmez
        """
        try:
            raw = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not raw or len(raw) < 10:
                return None
            df = pd.DataFrame(
                raw,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df.astype(float)
            return df
        except ccxt.BadSymbol:
            return None  # Sessiz atla
        except ccxt.NetworkError as e:
            print(f"[NET HATA] {symbol} {timeframe}: {e}")
            return None
        except ccxt.ExchangeError:
            return None  # Sessiz atla
        except Exception as e:
            print(f"[HATA] {symbol} {timeframe}: {e}")
            return None

    def fetch_coin_data(self, symbol):
        """
        Bir coin için tüm timeframe verisini çek
        Döndürür: {'1d': df, '4h': df, '1h': df, '15m': df} veya None
        """
        timeframes = {
            '1d': 100,
            '4h': 200,
            '1h': 200,
            '15m': 200,
        }

        data = {}
        for tf, limit in timeframes.items():
            df = self.fetch_ohlcv(symbol, tf, limit=limit)
            if df is not None and len(df) >= 30:
                data[tf] = df
            time.sleep(0.08)  # Rate limit

        if len(data) < 4:
            return None

        return data

    def get_correlated_pair(self, symbol):
        """
        SMT için korele parite
        """
        return CORRELATED_PAIRS.get(symbol, None)
