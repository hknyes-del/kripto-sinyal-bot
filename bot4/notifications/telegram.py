"""
Telegram bildirimleri - Geliştirilmiş versiyon
Sinyal + Backtest istatistikleri
"""

import requests
from config.settings import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from utils.helpers import format_price


def send_signal(signal):
    """
    Tam formatlı sinyal bildirimi gönder
    """
    if not signal:
        return None

    direction = signal['direction']
    dir_emoji = "🔴 SHORT" if direction == 'short' else "🟢 LONG"
    grade = signal['setup_grade']

    # Grade emoji
    grade_emoji = "🏆🏆" if grade == 'A++' else "🏆" if grade == 'A+' else "⭐"

    # Confluences
    conf = signal.get('confluences', {})
    breakdown = signal.get('breakdown', {})

    conf_lines = "\n".join([f"  {v}" for v in breakdown.values()])

    # SMT detayı
    smt_line = ""
    if signal.get('smt_detail'):
        smt_line = f"\n🔀 SMT: {signal['smt_detail'].get('description', '')}"

    # CRT detayı
    crt = signal.get('crt', {})
    crt_line = "✅ Aktif" if crt.get('found') else "❌ Yok"

    tp = signal['take_profits']
    entry = signal['entry_zone']

    message = f"""{grade_emoji} ICT SİNYALİ — {grade}

📊 {signal['symbol']} | {dir_emoji}
⭐ Skorlar: {signal['score']}/10 | Risk: %{signal.get('risk_pct','?')}

━━━━━━━━━━━━━━━━━━━━━
🎯 ENTRY BÖLGESİ
━━━━━━━━━━━━━━━━━━━━━
📍 Optimal: {format_price(entry['optimal'])}
📍 Zone: {format_price(entry['low'])} — {format_price(entry['high'])}

━━━━━━━━━━━━━━━━━━━━━
🛑 STOP LOSS
━━━━━━━━━━━━━━━━━━━━━
🛑 {format_price(signal['stop_loss'])}

━━━━━━━━━━━━━━━━━━━━━
💰 TAKE PROFIT
━━━━━━━━━━━━━━━━━━━━━
🎯 TP1: {format_price(tp['tp1']['price'])} (1:{tp['tp1']['rr']}) → %{tp['tp1']['close']} çık
🎯 TP2: {format_price(tp['tp2']['price'])} (1:{tp['tp2']['rr']}) → %{tp['tp2']['close']} çık
🎯 TP3: {format_price(tp['tp3']['price'])} (1:{tp['tp3']['rr']}) → %{tp['tp3']['close']} çık

━━━━━━━━━━━━━━━━━━━━━
📋 KONFLUANSLAR
━━━━━━━━━━━━━━━━━━━━━
{conf_lines}{smt_line}

━━━━━━━━━━━━━━━━━━━━━
🔄 CRT: {crt_line}
• Swing High: {format_price(crt.get('swing_high', 0))}
• Swing Low: {format_price(crt.get('swing_low', 0))}
• ChoCH: {format_price(crt.get('choch_price', 0))}
• Likidite: {crt.get('liquidity_taken','?')}
• Hedef: {crt.get('next_target','?')}

⚠️ Bu bir sinyal değil, analiz çıktısıdır. Kendi analizinizi yapın."""

    return send_telegram_message(message)


def send_backtest_stats(tracker):
    """
    Backtest istatistiklerini gönder
    """
    message = tracker.format_stats_message()
    return send_telegram_message(message)


def send_alert(text):
    """
    Basit uyarı mesajı
    """
    return send_telegram_message(f"⚠️ {text}")


def send_startup_message(coin_count, scan_interval):
    """
    Bot başladığında bildirim
    """
    msg = f"""
🤖 ICT CRYPTO BOT BAŞLADI

📊 Taranacak coin: {coin_count}
⏱ Tarama aralığı: {scan_interval} dakika
🔍 Analiz: CRT + MSB + FVG + SMT + OB

Sinyaller geldikçe buraya bildirim alacaksınız.
"""
    return send_telegram_message(msg)


def send_telegram_message(text):
    """
    Telegram API'ye mesaj gönder
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Telegram HTML parse mode için özel karakterleri temizle
    safe_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': safe_text,
        'parse_mode': 'HTML'
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        result = response.json()
        if not result.get('ok'):
            print(f"[TELEGRAM] Hata: {result.get('description')}")
        return result
    except requests.Timeout:
        print("[TELEGRAM] Zaman aşımı")
        return None
    except Exception as e:
        print(f"[TELEGRAM] Hata: {e}")
        return None