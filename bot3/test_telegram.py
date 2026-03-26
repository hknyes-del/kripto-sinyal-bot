import asyncio
from bot.telegram_bot import telegram_bot
from config import config

async def test():
    print("🤖 Telegram bot test ediliyor...")
    
    # Botu başlat
    sonuc = await telegram_bot.baslat()
    print(f"Başlatma: {sonuc}")
    
    # Test mesajı gönder
    await telegram_bot.test_mesaji_gonder()
    
    # Fake sinyal oluştur
    test_sinyali = {
        'sembol': 'BTC/USDT',
        'zaman_dilimi': '1H',
        'yon': 'BULLISH',
        'guven_skoru': 95,
        'entry_fiyat': 50000,
        'stop_loss': 49500,
        'take_profit': [50500, 51000, 52000],
        'fvg_derinlik': 65.5,
        'msb_tip': 'CHoCH',
        'order_block': 'BULLISH_OB'
    }
    
    # Sinyal gönder
    await telegram_bot.sinyal_gonder_entegrasyon(test_sinyali)

asyncio.run(test())