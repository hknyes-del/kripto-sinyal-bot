# bot/telegram_bot.py
import logging
from telegram import Bot
from telegram.error import TelegramError
import asyncio

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str, chat_id: int):
        """Telegram bot başlat"""
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
        logger.info("✅ Telegram Bot oluşturuldu")
    
    async def baslat(self):
        """Bot başlat"""
        try:
            me = await self.bot.get_me()
            logger.info(f"✅ Telegram bot hazır: @{me.username}")
        except Exception as e:
            logger.error(f"❌ Telegram bot başlatma hatası: {e}")
    
    async def test_mesaji_gonder(self):
        """Test mesajı gönder"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="🚀 Kripto Sinyal Sistemi başlatıldı!\n\n✅ Sistem aktif ve tarama yapıyor..."
            )
            logger.info("✅ Test mesajı gönderildi")
        except Exception as e:
            logger.error(f"❌ Test mesajı gönderme hatası: {e}")
    
    def _sinyal_to_dict(self, sinyal):
        """Sinyal object'ini dictionary'e çevir"""
        if isinstance(sinyal, dict):
            return sinyal
        
        try:
            sinyal_dict = {
                'sembol': getattr(sinyal, 'sembol', 'N/A'),
                'timeframe': getattr(sinyal, 'timeframe', 'N/A'),
                'fiyat': getattr(sinyal, 'fiyat', 'N/A'),
                'yon': getattr(sinyal, 'yon', 'N/A'),
                'zaman': getattr(sinyal, 'zaman', 'N/A'),
                'tip': getattr(sinyal, 'tip', 'N/A'),
                'seviye': getattr(sinyal, 'seviye', 'N/A'),
                'guc': getattr(sinyal, 'guc', 'N/A'),
            }
            
            # ✅ Eğer tüm değerler N/A ise, object'in string temsilini al
            if all(v == 'N/A' for v in sinyal_dict.values()):
                sinyal_str = str(sinyal)
                logger.warning(f"⚠️ Boş sinyal object: {sinyal_str}")
                
                # Object'den bilgi çıkarmaya çalış
                if 'silver' in sinyal_str.lower() or 'zone' in sinyal_str.lower():
                    sinyal_dict['tip'] = 'SILVER_BULLET'
            
            return sinyal_dict
        except Exception as e:
            logger.error(f"❌ Sinyal dönüştürme hatası: {e}")
            return {}
    
    async def sinyal_gonder_msb(self, sinyal):
        """MSB sinyali gönder"""
        try:
            sinyal_dict = self._sinyal_to_dict(sinyal)
            
            mesaj = f"""
📍 **MSB SİNYALİ**

📊 Sembol: `{sinyal_dict.get('sembol', 'N/A')}`
⏱️ Timeframe: `{sinyal_dict.get('timeframe', 'N/A')}`
💰 Fiyat: `{sinyal_dict.get('fiyat', 'N/A')}`
📈 Yön: `{sinyal_dict.get('yon', 'N/A')}`
💪 Güç: `{sinyal_dict.get('guc', 'N/A')}`

⏰ Zaman: `{sinyal_dict.get('zaman', 'N/A')}`
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"✅ MSB sinyali gönderildi: {sinyal_dict.get('sembol', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ MSB sinyali gönderme hatası: {e}")
    
    async def sinyal_gonder_fvg(self, sinyal):
        """FVG sinyali gönder"""
        try:
            sinyal_dict = self._sinyal_to_dict(sinyal)
            
            mesaj = f"""
🎯 **FVG SİNYALİ**

📊 Sembol: `{sinyal_dict.get('sembol', 'N/A')}`
⏱️ Timeframe: `{sinyal_dict.get('timeframe', 'N/A')}`
💰 Fiyat: `{sinyal_dict.get('fiyat', 'N/A')}`
📈 Yön: `{sinyal_dict.get('yon', 'N/A')}`
💪 Güç: `{sinyal_dict.get('guc', 'N/A')}`

⏰ Zaman: `{sinyal_dict.get('zaman', 'N/A')}`
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"✅ FVG sinyali gönderildi: {sinyal_dict.get('sembol', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ FVG sinyali gönderme hatası: {e}")
    
    async def sinyal_gonder_silver(self, sinyal):
        """Silver Bullet sinyali gönder"""
        try:
            sinyal_dict = self._sinyal_to_dict(sinyal)
            
            # ✅ Boş Silver Bullet'ları filtrele
            if (sinyal_dict.get('fiyat') == 'N/A' and 
                sinyal_dict.get('yon') == 'N/A' and 
                sinyal_dict.get('guc') == 'N/A'):
                logger.debug(f"⏭️ Boş Silver Bullet sinyali filtrelendi: {sinyal_dict.get('sembol')}")
                return
            
            mesaj = f"""
🔫 **SILVER BULLET SİNYALİ**

📊 Sembol: `{sinyal_dict.get('sembol', 'N/A')}`
⏱️ Timeframe: `{sinyal_dict.get('timeframe', 'N/A')}`
💰 Fiyat: `{sinyal_dict.get('fiyat', 'N/A')}`
📈 Yön: `{sinyal_dict.get('yon', 'N/A')}`
💪 Güç: `{sinyal_dict.get('guc', 'N/A')}`

⏰ Zaman: `{sinyal_dict.get('zaman', 'N/A')}`
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Silver Bullet sinyali gönderildi: {sinyal_dict.get('sembol', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ Silver Bullet sinyali gönderme hatası: {e}")
    
    async def sinyal_gonder_crt(self, sinyal):
        """CRT Setup sinyali gönder (MSB + FVG + Silver Bullet)"""
        try:
            sinyal_dict = self._sinyal_to_dict(sinyal)
            
            mesaj = f"""
🔥 **CRT SETUP BULUNDU!**

📊 Sembol: `{sinyal_dict.get('sembol', 'N/A')}`
⏱️ Timeframe: `{sinyal_dict.get('timeframe', 'N/A')}`

✅ MSB: Var
✅ FVG: Var
✅ Silver Bullet: Var

🎯 **Setup Tipi:** MSB + FVG + Silver Bullet Kombinasyonu

⚠️ **Bu çok güçlü bir sinyal kombinasyonudur!**
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"✅ CRT sinyali gönderildi: {sinyal_dict.get('sembol', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ CRT sinyali gönderme hatası: {e}")
    
    async def sinyal_gonder_sniper(self, setup):
        """Sniper Setup sinyali gönder (HTF CRT -> LTF MSB -> LTF FVG)"""
        try:
            sembol = setup.get('sembol', 'N/A')
            tf_htf = setup.get('htf_timeframe', 'N/A')
            tf_ltf = setup.get('ltf_timeframe', 'N/A')
            yon = setup.get('yon', 'N/A')
            
            emoji = "🟢" if yon == 'BULLISH' else "🔴"
            islem_tipi = "LONG" if yon == 'BULLISH' else "SHORT"
            
            entry = setup.get('entry', 0)
            sl = setup.get('sl', 0)
            tp1 = setup.get('tp1', 0)
            tp2 = setup.get('tp2', 0)
            tp3 = setup.get('tp3', 0)
            likidite = setup.get('likidite', 0)
            
            mesaj = f"""
🎯 **SNIPER SETUP BULDUM!** {emoji}

📊 **Sembol:** `{sembol}`
📈 **İşlem Tipi:** `{islem_tipi}`
🕒 **HTF Analiz ({tf_htf}):** `CRT Yapısı Onaylandı`
🕒 **LTF Analiz ({tf_ltf}):** `MSB + FVG Onayı`

---
🚧 **GİRİŞ (ENTRY):** `{entry:.5f}`
🛑 **STOP LOSS:** `{sl:.5f}`

💎 **TAKE PROFIT 1:** `{tp1:.5f}`
💎 **TAKE PROFIT 2:** `{tp2:.5f}`
💎 **TAKE PROFIT 3:** `{tp3:.5f}`

💀 **HEDEF LİKİDİTE:** `{likidite:.5f}`
---

⚠️ **Not:** Yüksek zaman diliminden (HTF) gelen ana yön onayı ile düşük zaman diliminde (LTF) tetiklendi.
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"🚀 Sniper sinyali gönderildi: {sembol} {yon}")
        except Exception as e:
            logger.error(f"❌ Sniper sinyali gönderme hatası: {e}")

    async def sinyal_gonder_sweep(self, setup):
        """Session/Daily Sweep sinyali gönder (1.5 RR Hedefli)"""
        try:
            sembol = setup.get('sembol', 'N/A')
            seviye_tipi = setup.get('seviye_tipi', 'N/A')
            yon = setup.get('yon', 'N/A')
            entry = setup.get('entry', 0)
            sl = setup.get('sl', 0)
            
            # ✅ Sabit 1.5 RR Hesaplama
            risk = abs(entry - sl)
            target_rr = 1.5
            tp_rr = entry + (risk * target_rr) if yon == 'BULLISH' else entry - (risk * target_rr)
            
            emoji = "💎" if yon == 'BULLISH' else "🐻"
            islem_tipi = "LONG" if yon == 'BULLISH' else "SHORT"
            
            mesaj = f"""
⚡ **SESSION SWEEP Sniper!** {emoji}

📊 **Sembol:** `{sembol}`
⚡ **Likidite:** `{seviye_tipi} Süpürüldü`
📈 **Yön:** `{islem_tipi}`

---
🚧 **GİRİŞ:** `{entry:.5f}`
🛑 **STOP:** `{sl:.5f}` (Sweep Low/High)

💰 **HEDEF (1.5 RR):** `{tp_rr:.5f}` ✅
---

⚠️ **Strateji:** Likidite süpürme sonrası LTF MSB onayı ile 1.5 RR hedefli hızlı işlem.
"""
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='Markdown'
            )
            logger.info(f"⚡ Sweep sinyali gönderildi: {sembol} {seviye_tipi}")
        except Exception as e:
            logger.error(f"❌ Sweep sinyali gönderme hatası: {e}")

    async def durdur(self):
        """Bot'u durdur"""
        try:
            logger.info("🛑 Telegram bot kapatılıyor...")
            logger.info("✅ Telegram bot kapatıldı")
        except Exception as e:
            logger.error(f"❌ Telegram bot kapatma hatası: {e}")

# Bot instance'ı oluştur
from bot3.config import config as bot3_config
telegram_bot = TelegramBot(
    token=bot3_config.TELEGRAM_BOT_TOKEN,
    chat_id=int(bot3_config.TELEGRAM_CHAT_ID)
)
