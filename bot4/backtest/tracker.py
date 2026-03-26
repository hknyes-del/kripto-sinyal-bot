"""
Backtest Takip Sistemi
Son 20 sinyalin performansını takip eder ve başarı oranını hesaplar
"""

import json
import os
from datetime import datetime


BACKTEST_FILE = os.path.join(os.path.dirname(__file__), 'history.json')


class BacktestTracker:
    def __init__(self, max_signals=20):
        self.max_signals = max_signals
        self.history = self._load_history()

    def _load_history(self):
        """
        Önceki sinyalleri dosyadan yükle
        """
        if os.path.exists(BACKTEST_FILE):
            try:
                with open(BACKTEST_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self):
        """
        Sinyalleri dosyaya kaydet
        """
        try:
            os.makedirs(os.path.dirname(BACKTEST_FILE), exist_ok=True)
            with open(BACKTEST_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[BACKTEST] Kaydetme hatası: {e}")

    def add_signal(self, signal):
        """
        Yeni sinyal ekle
        """
        record = {
            'id': len(self.history) + 1,
            'timestamp': datetime.now().isoformat(),
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'setup_grade': signal['setup_grade'],
            'score': signal['score'],
            'entry': signal['entry_zone']['optimal'],
            'stop_loss': signal['stop_loss'],
            'tp1': signal['take_profits']['tp1']['price'],
            'tp2': signal['take_profits']['tp2']['price'],
            'tp3': signal['take_profits']['tp3']['price'],
            'status': 'OPEN',       # OPEN, TP1_HIT, TP2_HIT, TP3_HIT, SL_HIT
            'result': None,          # 'WIN' / 'LOSS'
            'pnl_rr': None,          # Gerçekleşen R:R
            'checked_at': None,
        }

        self.history.append(record)

        # Son max_signals kadar tut
        if len(self.history) > self.max_signals:
            self.history = self.history[-self.max_signals:]

        self._save_history()
        return record['id']

    def update_signal_result(self, signal_id, status, pnl_rr=None):
        """
        Sinyalin sonucunu güncelle
        status: 'TP1_HIT', 'TP2_HIT', 'TP3_HIT', 'SL_HIT'
        """
        for record in self.history:
            if record['id'] == signal_id:
                record['status'] = status
                record['result'] = 'WIN' if 'TP' in status else 'LOSS'
                record['pnl_rr'] = pnl_rr
                record['checked_at'] = datetime.now().isoformat()
                self._save_history()
                return True
        return False

    def check_and_update_open_signals(self, current_prices: dict):
        """
        Açık sinyalleri mevcut fiyatlarla karşılaştır ve güncelle
        current_prices: {'BTC/USDT': 65000.0, ...}
        """
        updated = []

        for record in self.history:
            if record['status'] != 'OPEN':
                continue

            symbol = record['symbol']
            if symbol not in current_prices:
                continue

            price = current_prices[symbol]
            direction = record['direction']
            entry = record['entry']
            sl = record['stop_loss']
            tp1 = record['tp1']
            tp2 = record['tp2']
            tp3 = record['tp3']

            # Risk hesapla
            risk = abs(entry - sl)
            if risk == 0:
                continue

            if direction == 'long':
                if price <= sl:
                    self.update_signal_result(record['id'], 'SL_HIT', -1.0)
                    updated.append(record)
                elif price >= tp3:
                    rr = (price - entry) / risk
                    self.update_signal_result(record['id'], 'TP3_HIT', round(rr, 2))
                    updated.append(record)
                elif price >= tp2:
                    rr = (price - entry) / risk
                    self.update_signal_result(record['id'], 'TP2_HIT', round(rr, 2))
                    updated.append(record)
                elif price >= tp1:
                    rr = (price - entry) / risk
                    self.update_signal_result(record['id'], 'TP1_HIT', round(rr, 2))
                    updated.append(record)

            elif direction == 'short':
                if price >= sl:
                    self.update_signal_result(record['id'], 'SL_HIT', -1.0)
                    updated.append(record)
                elif price <= tp3:
                    rr = (entry - price) / risk
                    self.update_signal_result(record['id'], 'TP3_HIT', round(rr, 2))
                    updated.append(record)
                elif price <= tp2:
                    rr = (entry - price) / risk
                    self.update_signal_result(record['id'], 'TP2_HIT', round(rr, 2))
                    updated.append(record)
                elif price <= tp1:
                    rr = (entry - price) / risk
                    self.update_signal_result(record['id'], 'TP1_HIT', round(rr, 2))
                    updated.append(record)

        return updated

    def get_stats(self):
        """
        İstatistikleri hesapla ve döndür
        """
        closed = [r for r in self.history if r['status'] != 'OPEN']
        wins = [r for r in closed if r['result'] == 'WIN']
        losses = [r for r in closed if r['result'] == 'LOSS']

        total = len(closed)
        win_count = len(wins)
        win_rate = (win_count / total * 100) if total > 0 else 0

        avg_rr = 0
        if wins:
            rr_values = [r['pnl_rr'] for r in wins if r['pnl_rr'] is not None]
            avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0

        return {
            'total_signals': len(self.history),
            'closed_signals': total,
            'open_signals': len(self.history) - total,
            'wins': win_count,
            'losses': len(losses),
            'win_rate': round(win_rate, 1),
            'avg_rr': round(avg_rr, 2),
            'last_5': self.history[-5:][::-1]  # Son 5 sinyal (yeniden eskiye)
        }

    def format_stats_message(self):
        """
        Telegram için istatistik mesajı
        """
        stats = self.get_stats()

        win_emoji = "🟢" if stats['win_rate'] >= 70 else "🟡" if stats['win_rate'] >= 50 else "🔴"

        msg = f"""
📊 BACKTEST RAPORU (Son {self.max_signals} Sinyal)

{win_emoji} Başarı Oranı: %{stats['win_rate']}
✅ Kazanan: {stats['wins']}
❌ Kaybeden: {stats['losses']}
⏳ Açık: {stats['open_signals']}
📈 Ort. R:R: 1:{stats['avg_rr']}
"""
        return msg
