"""
ICT Crypto Signal Bot - Ana Döngü
100 coin tarar, ICT analizi yapar, Telegram sinyal gönderir
"""

import time
import os
from datetime import datetime

from config.settings import SCAN_INTERVAL_MINUTES, TOTAL_COINS_TO_SCAN
from data.fetcher import BinanceDataFetcher
from signals.generator import SignalGenerator
from backtest.tracker import BacktestTracker
from notifications.telegram import send_signal, send_backtest_stats, send_alert, send_startup_message


def main():
    print("=" * 60)
    print("  ICT CRYPTO SIGNAL BOT v2.0")
    print("  CRT + MSB + FVG + SMT + Order Block")
    print("=" * 60)
    print(f"  Tarama aralığı : {SCAN_INTERVAL_MINUTES} dakika")
    print(f"  Coin sayısı    : {TOTAL_COINS_TO_SCAN}")
    print(f"  Başlangıç      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Bileşenler
    fetcher = BinanceDataFetcher()
    generator = SignalGenerator()
    backtest = BacktestTracker(max_signals=20)

    # Telegram başlangıç mesajı
    coins = fetcher.fetch_top_coins(TOTAL_COINS_TO_SCAN)
    send_startup_message(len(coins), SCAN_INTERVAL_MINUTES)

    scan_count = 0

    while True:
        try:
            scan_count += 1
            now = datetime.now()
            print(f"\n{'='*60}")
            print(f"  [{now.strftime('%H:%M:%S')}] Tarama #{scan_count} başlıyor...")
            print(f"{'='*60}")

            signals_found = 0
            current_prices = {}  # Backtest güncellemesi için

            for i, symbol in enumerate(coins):
                try:
                    print(f"  [{i+1:3}/{len(coins)}] {symbol:<15}", end="", flush=True)

                    # Veri çek
                    data = fetcher.fetch_coin_data(symbol)
                    if not data:
                        print(" ⚠ Veri yok")
                        continue

                    # Güncel fiyatı kaydet (backtest için)
                    current_prices[symbol] = float(data['1h']['close'].iloc[-1])

                    # Korele parite verisini çek (SMT için)
                    corr_symbol = fetcher.get_correlated_pair(symbol)
                    data_corr = None
                    if corr_symbol:
                        data_corr = fetcher.fetch_coin_data(corr_symbol)

                    # Sinyal analizi
                    signal = generator.analyze_coin(symbol, data, data_corr)

                    if signal:
                        signals_found += 1
                        grade = signal['setup_grade']
                        score = signal['score']
                        direction = signal['direction'].upper()

                        print(f" ✅ {direction} {grade} ({score}/10)")

                        # Telegram gönder
                        send_signal(signal)

                        # Backtest'e kaydet
                        backtest.add_signal(signal)

                        # Küçük bekleme (ani flood önleme)
                        time.sleep(1.0)

                    else:
                        print(" —")

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f" ❌ Hata: {e}")
                    continue

            # Açık sinyalleri güncelle
            updated = backtest.check_and_update_open_signals(current_prices)
            if updated:
                print(f"\n  📊 {len(updated)} sinyal güncellendi")
                # Her 5 taramada bir istatistik gönder
                if scan_count % 5 == 0:
                    send_backtest_stats(backtest)

            # Özet
            stats = backtest.get_stats()
            print(f"\n  Tarama tamamlandı!")
            print(f"  Bulunan sinyal : {signals_found}")
            print(f"  Başarı oranı   : %{stats['win_rate']} ({stats['wins']}/{stats['closed_signals']})")
            print(f"  Sonraki tarama : {SCAN_INTERVAL_MINUTES} dakika sonra")

            # Bekleme
            time.sleep(SCAN_INTERVAL_MINUTES * 60)

        except KeyboardInterrupt:
            print("\n\n  Bot durduruldu. Güle güle!")
            send_alert("Bot manuel olarak durduruldu.")
            break

        except Exception as e:
            err_msg = f"Ana döngü hatası: {e}"
            print(f"\n  ❌ {err_msg}")
            send_alert(err_msg)
            print("  60 saniye bekleniyor...")
            time.sleep(60)


if __name__ == "__main__":
    main()