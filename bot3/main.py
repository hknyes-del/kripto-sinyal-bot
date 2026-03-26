"""
bot3/main.py — Egitim kurallariyla yeniden yazildi.
GreenBot ile ayni mantik, bot3'e ozgu import yollari.
"""
from bot.telegram_bot import telegram_bot
from veri.veri_topla import veri_topla
from sinyaller.msb_detector import msb_detector
from sinyaller.fvg_retrace import fvg_detector
from ict.bias_detector import bias_detector
from ict.session_times import session_times
from crt.crt_detector import crt_detector
from crt.smt_detector import smt_detector
import asyncio
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KORELE_CIFTLER = {
    'BTCUSDT': 'ETHUSDT', 'ETHUSDT': 'BTCUSDT',
    'SOLUSDT': 'AVAXUSDT', 'EURUSDT': 'GBPUSDT',
}


class KriptoSinyalSistemi:

    def __init__(self):
        self.calistiriliyor = False
        self.son_sinyaller  = {}
        self.sinyal_cooldown = 300

    def _sinyal_hash(self, sembol, tf, tip):
        return f"{sembol}_{tf}_{tip}"

    def _sinyal_gonderildi_mi(self, sembol, tf, tip):
        h = self._sinyal_hash(sembol, tf, tip)
        if h in self.son_sinyaller:
            if datetime.now() - self.son_sinyaller[h] < timedelta(seconds=self.sinyal_cooldown):
                return True
        return False

    def _sinyal_kaydet(self, sembol, tf, tip):
        self.son_sinyaller[self._sinyal_hash(sembol, tf, tip)] = datetime.now()

    async def baslat(self):
        logger.info("SNIPER SISTEMI v3.0 BASLATIYOR (Egitim Versiyonu)...")

        try:
            await telegram_bot.baslat()
            await telegram_bot.test_mesaji_gonder()
        except Exception as e:
            logger.error(f"Telegram hatasi: {e}")

        from config import config
        self.calistiriliyor = True

        while self.calistiriliyor:
            try:
                # Pazartesi Fog of War
                if datetime.now().weekday() == 0:
                    logger.info("Pazartesi - Fog of War, 1 saat bekleniyor")
                    await asyncio.sleep(3600)
                    continue

                islem_ok, uyari = session_times.islem_yapilabilir_mi()
                if not islem_ok:
                    logger.debug(f"Seans uygun degil: {uyari}")
                    await asyncio.sleep(300)
                    continue

                seans       = session_times.su_an_ne_seans()
                seans_skoru = seans.get('kalite_skoru', 0)
                is_cuma     = datetime.now().weekday() == 4

                logger.info(f"TARAMA | {seans['seans_label']}")

                # SMT Bias (BTC-ETH)
                smt_bias = None
                try:
                    df_btc = veri_topla.veri_cek_rest('BTCUSDT', '1h', 20)
                    df_eth = veri_topla.veri_cek_rest('ETHUSDT', '1h', 20)
                    if not df_btc.empty and not df_eth.empty:
                        uyumsuzluklar = smt_detector.analiz_et({'BTCUSDT': df_btc, 'ETHUSDT': df_eth})
                        if uyumsuzluklar:
                            smt_bias = uyumsuzluklar[0].tip
                except:
                    pass

                sinyal_sayisi = 0
                for sembol in config.TARGET_SYMBOLS:
                    try:
                        # Veri cek
                        df_1d  = veri_topla.veri_cek_rest(sembol, '1d', 100)
                        df_1h  = veri_topla.veri_cek_rest(sembol, '1h', 200)
                        df_15m = veri_topla.veri_cek_rest(sembol, '15m', 200)

                        if df_1d.empty or df_1h.empty:
                            continue

                        # HTF Bias
                        bias_result = bias_detector.analiz_et(df_1d)
                        if bias_result.yon == 'NEUTRAL':
                            continue

                        # MSB - bias yonune gore filtreli
                        htf_str  = 'BULLISH' if bias_result.yon == 'BULLISH' else 'BEARISH'
                        msb_list = msb_detector.analiz_et(df_1h, sembol, '1h', htf_str)

                        for msb in msb_list:
                            if self._sinyal_gonderildi_mi(sembol, '1h', 'MSB'):
                                break
                            guven = msb.guven_skoru
                            if seans_skoru == 3: guven += 5
                            if bias_result.a_plus_uyumlu: guven += 5

                            if guven >= 75:
                                try:
                                    await telegram_bot.sinyal_gonder_msb(msb)
                                    self._sinyal_kaydet(sembol, '1h', 'MSB')
                                    sinyal_sayisi += 1
                                    logger.info(f"MSB: {sembol} %{guven:.0f}")
                                except Exception as e:
                                    logger.debug(f"MSB mesaj hatasi: {e}")

                        # FVG - MSB varsa
                        if msb_list and not df_15m.empty:
                            fvg_list = fvg_detector.analiz_et(df_15m, sembol, '15m', msb_list)
                            for fvg in fvg_list:
                                if self._sinyal_gonderildi_mi(sembol, '15m', 'FVG'):
                                    break
                                guven = fvg.guven_skoru
                                if fvg.sart_puan == 3: guven += 5
                                if fvg.bias_pd_uyumu:  guven += 5
                                if seans_skoru == 3:   guven += 5

                                if guven >= 75:
                                    try:
                                        await telegram_bot.sinyal_gonder_fvg(fvg)
                                        self._sinyal_kaydet(sembol, '15m', 'FVG')
                                        sinyal_sayisi += 1
                                    except Exception as e:
                                        logger.debug(f"FVG mesaj hatasi: {e}")

                    except Exception as e:
                        logger.error(f"{sembol} hatasi: {e}")

                logger.info(f"Tarama bitti | {sinyal_sayisi} sinyal")
                await asyncio.sleep(300)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Ana dongu hatasi: {e}")
                await asyncio.sleep(60)

    def durdur(self):
        self.calistiriliyor = False


async def main():
    sistem = KriptoSinyalSistemi()
    try:
        await sistem.baslat()
    except KeyboardInterrupt:
        logger.info("Durduruldu")
    finally:
        sistem.durdur()


if __name__ == "__main__":
    asyncio.run(main())
