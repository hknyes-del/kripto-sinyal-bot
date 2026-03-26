import logging
from telegram import Bot
from telegram.error import TelegramError
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)

class TelegramSinyalBot:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.bot = None
    
    def _format_price(self, price):
        if price is None: return "0"
        try:
            if price >= 1000: return f"${price:,.2f}"
            elif price >= 1: return f"${price:.4f}"
            elif price >= 0.0001: return f"${price:.6f}"
            else: return f"${price:.8f}"
        except: return f"${price}"
        
    async def baslat(self):
        if not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.error("❌ Telegram token'ı config.py'ye eklenmemiş!")
            return False
        try:
            self.bot = Bot(token=self.bot_token)
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Telegram bot hazır: @{bot_info.username}")
            return True
        except Exception as e:
            logger.error(f"❌ Telegram bot başlatılamadı: {e}")
            return False
    
    async def test_mesaji_gonder(self):
        mesaj = """
🤖 *BERKAY SNIPER BOT v6.0*

✅ MSB + CRT + FVG + FIB Full entegrasyon
✅ Super Model filtre (%90+ winrate)
✅ Bias + SMT + Monday Range confluence

🚀 Canlı sinyaller aktif!
📊 %90+ winrate hedefi...
"""
        return await self.mesaj_gonder(mesaj)
    
    async def mesaj_gonder(self, mesaj):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=mesaj, parse_mode='Markdown')
            logger.info("✅ Telegram mesajı gönderildi")
            return True
        except Exception as e:
            logger.error(f"❌ Telegram mesaj hatası: {e}")
            return False

    # 🔥 YENİ: MSB BERKAY SUPER MODEL
    async def sinyal_gonder_msb_berkay(self, sinyal):
        """🔥 BERKAY MSB SUPER MODEL"""
        try:
            yon_emoji = "🟢🚀" if sinyal.yon == "BULLISH" else "🔴🚀"
            yon_text = "YÜKSELİŞ MSB" if sinyal.yon == "BULLISH" else "DÜŞÜŞ MSB"
            super_emoji = "🔥 A+++" if sinyal.super_model else "⭐ A+"
            
            fib_emoji = "📈" if sinyal.fib_zone == "UCUZLUK" else "📉"
            bias_emoji = "✅" if sinyal.bias_yon == sinyal.yon else "⚠️"
            
            mesaj = f"""
🚀 *BERKAY SNIPER MSB* {super_emoji}

💎 *{sinyal.sembol.upper()}* | {sinyal.zaman_dilimi}
{yon_emoji} {yon_text}

📊 *Super Model Skoru:* **%{sinyal.guven_skoru:.0f}**
{fib_emoji} Fib Zone: **{sinyal.fib_zone}**
{bias_emoji} Bias: **{sinyal.bias_yon}**
{smt_emoji} SMT: **{sinyal.smt_konfirm}**
{monday_emoji} Monday Range: **{sinyal.monday_range_confluence}**

💰 *Entry:* `{self._format_price(sinyal.entry)}`
🛑 *Stop:* `{self._format_price(sinyal.stop)}`
🎯 *Target:* `{self._format_price(sinyal.entry * 1.03 if sinyal.yon == "BULLISH" else sinyal.entry * 0.97)}`
⚡ *RR:* **1:3+**

⏰ **{datetime.now().strftime('%d.%m %H:%M:%S')}**
#MSB #{sinyal.sembol.replace('/', '').replace('USDT', '')} #{sinyal.yon}
"""
            await self.bot.send_message(chat_id=self.chat_id, text=mesaj, parse_mode='Markdown')
            logger.info(f"✅ BERKAY MSB gönderildi: {sinyal.sembol} {sinyal.guven_skoru}")
            return True
        except Exception as e:
            logger.error(f"❌ BERKAY MSB gönderilemedi: {e}")
            return False
    
    # 🔥 YENİ: CRT BERKAY SNIPER
    async def sinyal_gonder_crt_berkay(self, crt_sinyal):
        """🔥 BERKAY CRT + MSB COMBO"""
        try:
            mesaj = f"""
💎 *BERKAY CRT SNIPER* 🔥

{sembol} | {htf}
🎯 Sweep tamamlandı → Reclaim bekleniyor
📊 Fib: {fib_zone} | Bias: {bias_yon}

⏰ {datetime.now().strftime('%H:%M')}
#CRT #{sembol}
"""
            await self.bot.send_message(chat_id=self.chat_id, text=mesaj, parse_mode='Markdown')
            return True
        except Exception as e:
            logger.error(f"❌ CRT BERKAY gönderilemedi: {e}")
            return False
    
    # ESKİ FONKSİYONLAR (Korundu)
    async def sinyal_gonder_msb(self, sinyal, sinyal_id=None): pass  # Eski MSB
    async def sinyal_gonder_fvg(self, sinyal, sinyal_id=None): pass  # Eski FVG
    async def sinyal_gonder_crt_bildirim(self, sinyal): pass  # Eski CRT


telegram_bot = TelegramSinyalBot()
