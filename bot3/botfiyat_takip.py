from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import logging
from datetime import datetime

from config import config
from veritabani import sinyal_db

logger = logging.getLogger(__name__)

class FiyatTakipBotu:
    """Telegram üzerinden TP/SL takibi"""
    
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.application = None
    
    async def baslat(self):
        """Botu başlat"""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Komutları ekle
        self.application.add_handler(CommandHandler("tp1", self.tp1_komutu))
        self.application.add_handler(CommandHandler("tp2", self.tp2_komutu))
        self.application.add_handler(CommandHandler("tp3", self.tp3_komutu))
        self.application.add_handler(CommandHandler("sl", self.sl_komutu))
        self.application.add_handler(CommandHandler("iptal", self.iptal_komutu))
        self.application.add_handler(CommandHandler("rapor", self.rapor_komutu))
        self.application.add_handler(CommandHandler("istatistik", self.istatistik_komutu))
        
        await self.application.initialize()
        await self.application.start()
        
        # Webhook ayarla
        await self.application.bot.set_webhook(url=f"https://api.telegram.org/bot{self.bot_token}/setWebhook")
        
        logger.info("✅ Fiyat Takip Botu başlatıldı")
    
    async def tp1_komutu(self, update, context):
        """TP1 oldu - /tp1 123"""
        try:
            sinyal_id = int(context.args[0])
            fiyat = float(context.args[1]) if len(context.args) > 1 else 0
            
            if sinyal_db.sinyal_guncelle(sinyal_id, 'TP1', fiyat):
                await update.message.reply_text(f"✅ Sinyal #{sinyal_id} TP1 olarak kaydedildi!")
            else:
                await update.message.reply_text(f"❌ Sinyal #{sinyal_id} bulunamadı!")
        except:
            await update.message.reply_text("❌ Kullanım: /tp1 [sinyal_id] [fiyat]")
    
    async def tp2_komutu(self, update, context):
        """TP2 oldu"""
        try:
            sinyal_id = int(context.args[0])
            fiyat = float(context.args[1]) if len(context.args) > 1 else 0
            
            if sinyal_db.sinyal_guncelle(sinyal_id, 'TP2', fiyat):
                await update.message.reply_text(f"✅ Sinyal #{sinyal_id} TP2 olarak kaydedildi!")
            else:
                await update.message.reply_text(f"❌ Sinyal #{sinyal_id} bulunamadı!")
        except:
            await update.message.reply_text("❌ Kullanım: /tp2 [sinyal_id] [fiyat]")
    
    async def tp3_komutu(self, update, context):
        """TP3 oldu"""
        try:
            sinyal_id = int(context.args[0])
            fiyat = float(context.args[1]) if len(context.args) > 1 else 0
            
            if sinyal_db.sinyal_guncelle(sinyal_id, 'TP3', fiyat):
                await update.message.reply_text(f"✅ Sinyal #{sinyal_id} TP3 olarak kaydedildi! 🏆")
            else:
                await update.message.reply_text(f"❌ Sinyal #{sinyal_id} bulunamadı!")
        except:
            await update.message.reply_text("❌ Kullanım: /tp3 [sinyal_id] [fiyat]")
    
    async def sl_komutu(self, update, context):
        """Stop Loss oldu"""
        try:
            sinyal_id = int(context.args[0])
            fiyat = float(context.args[1]) if len(context.args) > 1 else 0
            
            if sinyal_db.sinyal_guncelle(sinyal_id, 'SL', fiyat):
                await update.message.reply_text(f"⚠️ Sinyal #{sinyal_id} SL olarak kaydedildi!")
            else:
                await update.message.reply_text(f"❌ Sinyal #{sinyal_id} bulunamadı!")
        except:
            await update.message.reply_text("❌ Kullanım: /sl [sinyal_id] [fiyat]")
    
    async def rapor_komutu(self, update, context):
        """Günlük rapor"""
        rapor = sinyal_db.gunluk_rapor()
        await update.message.reply_text(rapor, parse_mode='Markdown')
    
    async def istatistik_komutu(self, update, context):
        """Tüm istatistikler"""
        stats = sinyal_db.istatistik()
        if not stats:
            await update.message.reply_text("Henüz sinyal yok.")
            return
        
        mesaj = f"""
📊 *SİNYAL İSTATİSTİKLERİ*

📈 Toplam Sinyal: {stats['toplam']}
🟢 Aktif: {stats['aktif']}

🎯 *TP SEVİYELERİ*
✅ TP1: {stats['tp1']}
✅✅ TP2: {stats['tp2']}
✅✅✅ TP3: {stats['tp3']}
❌ SL: {stats['sl']}
⏸️ İptal: {stats['iptal']}

📊 *PERFORMANS*
⭐ Başarı Oranı: %{stats['basari_orani']}
💰 Ortalama Kar: %{stats['ortalama_kar']}
"""
        await update.message.reply_text(mesaj, parse_mode='Markdown')

fiyat_takip = FiyatTakipBotu()