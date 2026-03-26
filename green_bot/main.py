"""
green_bot/main.py — Egitim kurallariyla yeniden yazildi.

YENI KURALLAR:
  - Pazartesi: Fog of War — tarama yok
  - Asya seasi: islem yapma
  - Bias yonu ile MSB/FVG yonu eslesmesi zorunlu
  - SHORT = PREMIUM, LONG = DISCOUNT (fib 0.5 kurali)
  - Seans kalitesi: Overlap en guclu (skor 3), Asya 0
  - TGIF (Cuma): ekstra uyari ile sinyal gonder
"""
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd

from config import config
from bot.telegram_bot import telegram_bot
from veri.veri_topla import veri_topla
from ict.bias_detector import bias_detector
from ict.session_times import session_times
from sinyaller.crt_detector import crt_detector
from sinyaller.msb_detector import msb_detector, MSBSinyali
from sinyaller.fvg_detector import fvg_detector, FVGSinyali

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Korele parite ciftleri (SMT icin)
KORELE_CIFTLER = {
    'BTCUSDT': 'ETHUSDT',
    'ETHUSDT': 'BTCUSDT',
    'SOLUSDT': 'AVAXUSDT',
    'EURUSDT': 'GBPUSDT',
}


class SniperBot:

    def __init__(self):
        self.running              = False
        self.cooldowns            = {}
        self.cooldown_sure        = 1800   # 30 dakika
        self.son_sinyaller        = {}
        logger.info("GREEN SIGNALS v8.0 - Egitim Versiyonu AKTIF")

    def _cooldown_var_mi(self, sembol: str) -> bool:
        if sembol not in self.cooldowns:
            return False
        return (datetime.now() - self.cooldowns[sembol]).total_seconds() < self.cooldown_sure

    def _cooldown_kaydet(self, sembol: str):
        self.cooldowns[sembol] = datetime.now()

    def _sinyal_gonderilebilir_mi(self, sembol: str, tip: str) -> bool:
        anahtar = f"{sembol}_{tip}"
        if anahtar in self.son_sinyaller:
            gecen = datetime.now() - self.son_sinyaller[anahtar]
            if gecen < timedelta(hours=2):
                return False
        self.son_sinyaller[anahtar] = datetime.now()
        return True

    def _format_price(self, price: float) -> str:
        try:
            if price >= 1000:    return f"${price:,.2f}"
            elif price >= 1:     return f"${price:.4f}"
            elif price >= 0.0001: return f"${price:.6f}"
            else:                 return f"${price:.8f}"
        except:
            return f"${price}"

    async def _coin_analiz(self, sembol: str):
        # ── Pazartesi Filtresi ──────────────────────────────
        if datetime.now().weekday() == 0:
            return   # Fog of War

        if self._cooldown_var_mi(sembol):
            return

        # ── Seans Filtresi ──────────────────────────────────
        islem_ok, seans_uyari = session_times.islem_yapilabilir_mi()
        if not islem_ok:
            logger.debug(f"{sembol}: {seans_uyari}")
            return

        seans      = session_times.su_an_ne_seans()
        is_cuma    = datetime.now().weekday() == 4
        seans_skoru = seans.get('kalite_skoru', 0)

        logger.info(f"GREEN ANALIZ: {sembol} | {seans['seans_label']}")

        try:
            # ── Veri ────────────────────────────────────────
            df_1d  = await veri_topla.veri_cek_rest(sembol, "1d",  100)
            df_4h  = await veri_topla.veri_cek_rest(sembol, "4h",  100)
            df_1h  = await veri_topla.veri_cek_rest(sembol, "1h",  200)
            df_15m = await veri_topla.veri_cek_rest(sembol, "15m", 200)

            if df_1d.empty or df_4h.empty or df_1h.empty:
                return

            # ── HTF Bias (1D) ────────────────────────────────
            # Egitim: Bias olmadan islem yapma
            bias_result = bias_detector.analiz_et(df_1d)
            market_yon  = bias_result.yon

            if market_yon == 'NEUTRAL':
                logger.debug(f"{sembol}: Bias NEUTRAL - atlandi")
                return

            # A++ icin STRONG bias zorunlu (STRONG_BULLISH / STRONG_BEARISH)
            # Zayif biasla da sinyal uretiyoruz ama guven dusuk
            a_plus_uyumlu = bias_result.a_plus_uyumlu

            # ── MSB (1H) — Bias yonune gore ─────────────────
            htf_bias_str = 'BULLISH' if market_yon == 'BULLISH' else 'BEARISH'
            msb_1h_list  = msb_detector.analiz_et(df_1h, sembol, "1h", htf_bias_str)

            if msb_1h_list and self._sinyal_gonderilebilir_mi(sembol, "MSB_1H"):
                for msb in msb_1h_list:
                    guven = msb.guven_skoru

                    # Seans bonusu
                    if seans_skoru == 3: guven += 5   # Overlap
                    elif seans_skoru == 2: guven += 2

                    # A++ bias uyumu bonusu
                    if a_plus_uyumlu: guven += 5

                    # TGIF uyarisi
                    tgif_notu = "\n📅 TGIF - Cuma kapanis likiditesi dikkat!" if is_cuma else ""

                    if guven >= 75:
                        try:
                            pd_notu = (
                                f"\n📍 Bias: {bias_result.bias} | "
                                f"{bias_result.pd_zone} "
                                f"(guc:{bias_result.pd_strength:.2f})"
                            )
                            await telegram_bot.sinyal_gonder_msb(msb)
                            self._cooldown_kaydet(sembol)
                            logger.info(f"GREEN MSB(1H): {sembol} %{guven:.0f} {seans['seans_label']}")
                        except Exception as e:
                            logger.error(f"MSB mesaj hatasi: {e}")
                            await telegram_bot.mesaj_gonder(
                                f"MSB: {sembol} {msb.yon} %{guven:.0f}{tgif_notu}"
                            )

            # ── FVG (15M) — Sadece MSB varsa ─────────────────
            # Egitim: FVG'nin 3 sarti olmali
            if msb_1h_list and not df_15m.empty:
                fvg_list = fvg_detector.analiz_et(df_15m, sembol, "15m", msb_1h_list)

                for fvg in fvg_list:
                    if not self._sinyal_gonderilebilir_mi(sembol, "FVG_15M"):
                        break
                    guven = fvg.guven_skoru

                    # FVG 3 sart bonusu
                    if fvg.sart_puan == 3: guven += 5

                    # Premium/Discount uyumu
                    if fvg.bias_pd_uyumu: guven += 5

                    if seans_skoru == 3: guven += 5
                    if a_plus_uyumlu:   guven += 5

                    if guven >= 75:
                        try:
                            await telegram_bot.sinyal_gonder_fvg(fvg)
                            logger.info(
                                f"GREEN FVG(15M): {sembol} %{guven:.0f} "
                                f"Sartlar:{fvg.sart_puan}/3"
                            )
                        except Exception as e:
                            logger.error(f"FVG mesaj hatasi: {e}")

            # ── CRT (4H) ─────────────────────────────────────
            crt_list = crt_detector.analiz_et(df_4h, sembol, "4h")
            for crt in crt_list:
                if not self._sinyal_gonderilebilir_mi(sembol, "CRT_4H"):
                    break
                try:
                    crt_mesaj = (
                        f"CRT TESPIT: {sembol}\n"
                        f"Yon: {crt.yon if hasattr(crt,'yon') else 'Bilinmiyor'}\n"
                        f"Bias: {bias_result.bias} | {bias_result.pd_zone}\n"
                        f"Seans: {seans['seans_label']}"
                    )
                    await telegram_bot.mesaj_gonder(crt_mesaj)
                    logger.info(f"GREEN CRT(4H): {sembol}")
                except Exception as e:
                    logger.debug(f"CRT mesaj hatasi: {e}")

        except Exception as e:
            logger.error(f"{sembol} analiz hatasi: {e}")

    async def _paralel_tarama(self):
        # Pazartesi kontrolu
        if datetime.now().weekday() == 0:
            logger.info("Pazartesi Fog of War - tarama yapilmadi")
            return

        if hasattr(self, '_tarama_devam') and self._tarama_devam:
            return
        self._tarama_devam = True

        seans = session_times.su_an_ne_seans()
        logger.info(
            f"GREEN TARAMA | {len(config.TARGET_SYMBOLS)} coin | "
            f"{seans['seans_label']} (skor:{seans['kalite_skoru']})"
        )

        gorevler = []
        for sembol in config.TARGET_SYMBOLS[:10]:
            g = asyncio.create_task(self._coin_analiz(sembol))
            gorevler.append(g)
            await asyncio.sleep(0.1)

        if gorevler:
            await asyncio.gather(*gorevler, return_exceptions=True)

        self._tarama_devam = False
        logger.info("GREEN TARAMA TAMAMLANDI")

    async def baslat(self):
        logger.info("GREEN SIGNALS v8.0 BASLATIYOR...")

        try:
            await telegram_bot.baslat()
            await telegram_bot.test_mesaji_gonder()
            logger.info("TELEGRAM BOT HAZIR")
        except Exception as e:
            logger.error(f"Telegram baslama hatasi: {e}")

        self.running   = True
        tarama_sayisi  = 0

        while self.running:
            try:
                tarama_sayisi += 1
                logger.info(f"TARAMA #{tarama_sayisi}")
                await self._paralel_tarama()
                logger.info("5 dakika bekleniyor...")
                await asyncio.sleep(300)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Ana dongu hatasi: {e}")
                await asyncio.sleep(60)

    async def durdur(self):
        self.running = False
        logger.info("GREEN SIGNALS DURDURULDU")


async def main():
    bot = SniperBot()
    try:
        await bot.baslat()
    except KeyboardInterrupt:
        logger.info("Kullanici durdurdu")
    finally:
        await bot.durdur()


if __name__ == "__main__":
    asyncio.run(main())
