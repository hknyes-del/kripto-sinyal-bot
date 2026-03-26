"""
╔══════════════════════════════════════════════════════════════╗
║       DOSYA 6: utils/calculations.py — P&L Hesap Motoru     ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Tüm finansal hesaplamaları merkezi olarak yönetir.
Gerçek zamanlı P&L, marjin seviyeleri, kaldıraç etkileri,
tasfiye fiyatları ve istatistik hesaplamalarını içerir.
"""

from config import (
    INITIAL_BALANCE, MARGIN_CALL_LEVEL,
    LIQUIDATION_LEVEL, TP_PARTIAL_CLOSE
)


# ═══════════════════════════════════════════════
#  KAR / ZARAR HESABI
# ═══════════════════════════════════════════════

def calculate_unrealized_pnl(direction: str, entry_price: float,
                              current_price: float, position_size: float,
                              leverage: int) -> dict:
    """
    Gerçekleşmemiş kar/zarar hesaplar.

    Args:
        direction:      "LONG" veya "SHORT"
        entry_price:    Giriş fiyatı
        current_price:  Güncel fiyat
        position_size:  Pozisyon büyüklüğü (coin miktarı)
        leverage:       Kaldıraç

    Returns:
        pnl_dollar:  $ cinsinden kar/zarar
        pnl_pct:     % cinsinden kar/zarar (marjine göre)
        roi_pct:     Gerçek ROI (kaldıraç dahil)
    """
    if direction == "LONG":
        price_change = current_price - entry_price
    else:   # SHORT
        price_change = entry_price - current_price

    pnl_dollar = price_change * position_size
    price_change_pct = (price_change / entry_price) * 100
    roi_pct = price_change_pct * leverage   # Kaldıraç etkisi

    return {
        "pnl_dollar":  round(pnl_dollar, 2),
        "pnl_pct":     round(price_change_pct, 4),
        "roi_pct":     round(roi_pct, 2),
        "is_profit":   pnl_dollar > 0,
        "price_change": round(price_change, 6),
    }


def calculate_realized_pnl(direction: str, entry_price: float,
                            exit_price: float, position_size: float,
                            margin_used: float, leverage: int,
                            fee_rate: float = 0.001) -> dict:
    """
    Kapatılan pozisyon için gerçekleşen kar/zarar hesaplar.
    fee_rate: İşlem ücreti oranı (varsayılan: %0.1 taker fee)
    """
    if direction == "LONG":
        price_diff = exit_price - entry_price
    else:
        price_diff = entry_price - exit_price

    position_value_entry = position_size * entry_price
    position_value_exit  = position_size * exit_price
    gross_pnl = price_diff * position_size

    # Giriş + çıkış komisyonu
    fees_entry = position_value_entry * fee_rate
    fees_exit  = position_value_exit  * fee_rate
    total_fees = fees_entry + fees_exit

    net_pnl   = gross_pnl - total_fees
    roi_pct   = (net_pnl / margin_used * 100) if margin_used > 0 else 0

    return {
        "gross_pnl":   round(gross_pnl, 4),
        "fees":        round(total_fees, 4),
        "net_pnl":     round(net_pnl, 4),
        "roi_pct":     round(roi_pct, 2),
        "is_profit":   net_pnl > 0,
        "price_diff":  round(price_diff, 6),
    }


# ═══════════════════════════════════════════════
#  POZİSYON BOYUTU HESABI
# ═══════════════════════════════════════════════

def calculate_position_size(margin: float, leverage: int,
                             price: float) -> dict:
    """
    Marjin ve kaldıraçtan pozisyon büyüklüğü hesaplar.

    Örnek: $100 marjin, 5x kaldıraç, BTC $44,000
    Pozisyon değeri: $500
    Coin miktarı: 500 / 44,000 = 0.01136 BTC
    """
    position_value = margin * leverage
    coin_amount    = position_value / price

    return {
        "margin":          round(margin, 2),
        "leverage":        leverage,
        "position_value":  round(position_value, 2),
        "coin_amount":     round(coin_amount, 8),
        "price":           price,
    }


# ═══════════════════════════════════════════════
#  TAFSİYE FİYATI HESABI
# ═══════════════════════════════════════════════

def calculate_liquidation_price(direction: str, entry_price: float,
                                 leverage: int,
                                 maintenance_margin_rate: float = 0.005) -> float:
    """
    Tasfiye fiyatını hesaplar.
    maintenance_margin_rate: Bakım marjini oranı (varsayılan: %0.5)

    Formül (basitleştirilmiş):
    LONG:  Liq. = entry × (1 - 1/leverage + maintenance_rate)
    SHORT: Liq. = entry × (1 + 1/leverage - maintenance_rate)
    """
    if direction == "LONG":
        liq_price = entry_price * (1 - (1 / leverage) + maintenance_margin_rate)
    else:
        liq_price = entry_price * (1 + (1 / leverage) - maintenance_margin_rate)

    return round(liq_price, 4)


# ═══════════════════════════════════════════════
#  MARJİN SEVİYESİ
# ═══════════════════════════════════════════════

def calculate_margin_level(equity: float, used_margin: float) -> dict:
    """
    Marjin seviyesini hesaplar ve risk durumunu belirler.

    Marjin Seviyesi = (Equity / Kullanılan Marjin) × 100

    Eşikler:
    >200%:  Güvenli     (Yeşil)
    150-200%: Dikkatli  (Sarı)
    120-150%: Uyarı     (Turuncu)
    100-120%: Tehlike   (Kırmızı) → Margin Call
    <100%:  Kritik     (Koyu Kırmızı) → Otomatik Tasfiye
    """
    if used_margin <= 0:
        return {"level": 9999.0, "status": "SAFE", "color": "🟢", "free_margin": equity}

    level = (equity / used_margin) * 100
    free_margin = equity - used_margin

    if level >= 200:
        status, color, msg = "SAFE", "🟢", "Güvenli"
    elif level >= 150:
        status, color, msg = "CAUTION", "🟡", "Dikkatli"
    elif level >= 120:
        status, color, msg = "WARNING", "🟠", "⚠️ Uyarı"
    elif level >= 100:
        status, color, msg = "DANGER", "🔴", "❗ Margin Call Riski"
    else:
        status, color, msg = "CRITICAL", "💀", "❌ MARGIN CALL!"

    return {
        "level":       round(level, 1),
        "status":      status,
        "color":       color,
        "message":     msg,
        "free_margin": round(free_margin, 2),
        "used_margin": round(used_margin, 2),
        "equity":      round(equity, 2),
        "is_margin_call": level < MARGIN_CALL_LEVEL,
        "is_liquidation": level < LIQUIDATION_LEVEL,
    }


# ═══════════════════════════════════════════════
#  HESAP ÖZETİ
# ═══════════════════════════════════════════════

def calculate_account_summary(balance: float, open_positions: list,
                               current_prices: dict) -> dict:
    """
    Tüm açık pozisyonları değerlendirerek hesap özetini çıkarır.

    open_positions: DB'den gelen pozisyon listesi
    current_prices: {pair: price} sözlüğü
    """
    total_margin  = 0.0
    total_unrealized = 0.0
    positions_detail = []

    for pos in open_positions:
        pair    = pos["pair"]
        price   = current_prices.get(pair, pos.get("entry_price", 0))
        pnl_data = calculate_unrealized_pnl(
            direction     = pos["direction"],
            entry_price   = pos["entry_price"],
            current_price = price,
            position_size = pos["position_size"],
            leverage      = pos["leverage"],
        )
        total_margin       += pos["margin_used"]
        total_unrealized   += pnl_data["pnl_dollar"]

        positions_detail.append({
            **pos,
            "current_price":    price,
            "unrealized_pnl":   pnl_data["pnl_dollar"],
            "unrealized_pct":   pnl_data["roi_pct"],
            "liq_price":        calculate_liquidation_price(
                                    pos["direction"], pos["entry_price"], pos["leverage"]
                                ),
        })

    # Equity = Serbest Bakiye + Kullanılan Marjin + Gerçekleşmemiş P&L
    equity         = balance + total_margin + total_unrealized
    margin_info    = calculate_margin_level(equity, total_margin)

    return {
        "balance":        round(balance, 2),
        "equity":         round(equity, 2),
        "used_margin":    round(total_margin, 2),
        "free_margin":    round(margin_info["free_margin"], 2),
        "unrealized_pnl": round(total_unrealized, 2),
        "margin_level":   margin_info["level"],
        "margin_status":  margin_info["status"],
        "margin_color":   margin_info["color"],
        "positions":      positions_detail,
        "position_count": len(open_positions),
    }


# ═══════════════════════════════════════════════
#  PNL İSTATİSTİKLERİ
# ═══════════════════════════════════════════════

def calculate_pnl_statistics(trades: list) -> dict:
    """
    Kapatılan işlemler listesinden kapsamlı istatistikler hesaplar.
    Sharpe ratio, profit factor, drawdown dahil.
    """
    if not trades:
        return _empty_stats()

    pnls       = [t.get("net_pnl", 0) for t in trades]
    wins       = [p for p in pnls if p > 0]
    losses     = [p for p in pnls if p < 0]

    total       = len(pnls)
    win_count   = len(wins)
    loss_count  = len(losses)
    win_rate    = (win_count / total * 100) if total > 0 else 0

    total_pnl   = sum(pnls)
    gross_profit = sum(wins)  if wins   else 0
    gross_loss   = abs(sum(losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    avg_win  = (gross_profit / win_count)  if win_count   > 0 else 0
    avg_loss = (gross_loss   / loss_count) if loss_count  > 0 else 0

    best_trade  = max(pnls)
    worst_trade = min(pnls)

    # ─── Maximum Drawdown ─────────────────────────
    cumulative = 0
    peak       = 0
    max_dd     = 0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_dd:
            max_dd = drawdown

    # ─── Sharpe Oranı (basit) ─────────────────────
    import math
    avg_pnl = sum(pnls) / total if total > 0 else 0
    if total > 1:
        variance = sum((p - avg_pnl) ** 2 for p in pnls) / (total - 1)
        std_dev  = math.sqrt(variance)
        sharpe   = round((avg_pnl / std_dev) if std_dev > 0 else 0, 2)
    else:
        sharpe = 0

    # ─── En uzun kazanma/kaybetme serisi ──────────
    max_win_streak = max_lose_streak = 0
    cur_win = cur_lose = 0
    for p in pnls:
        if p > 0:
            cur_win += 1;  cur_lose = 0
            max_win_streak = max(max_win_streak, cur_win)
        else:
            cur_lose += 1; cur_win = 0
            max_lose_streak = max(max_lose_streak, cur_lose)

    return {
        "total_trades":    total,
        "win_count":       win_count,
        "loss_count":      loss_count,
        "win_rate":        round(win_rate, 1),
        "total_pnl":       round(total_pnl, 2),
        "gross_profit":    round(gross_profit, 2),
        "gross_loss":      round(gross_loss, 2),
        "profit_factor":   round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "avg_win":         round(avg_win, 2),
        "avg_loss":        round(avg_loss, 2),
        "best_trade":      round(best_trade, 2),
        "worst_trade":     round(worst_trade, 2),
        "max_drawdown":    round(max_dd, 2),
        "sharpe_ratio":    sharpe,
        "max_win_streak":  max_win_streak,
        "max_lose_streak": max_lose_streak,
        "avg_pnl":         round(avg_pnl, 2),
    }


def _empty_stats() -> dict:
    """İşlem yokken döndürülen boş istatistik."""
    return {
        "total_trades": 0, "win_count": 0, "loss_count": 0,
        "win_rate": 0, "total_pnl": 0, "gross_profit": 0,
        "gross_loss": 0, "profit_factor": 0, "avg_win": 0,
        "avg_loss": 0, "best_trade": 0, "worst_trade": 0,
        "max_drawdown": 0, "sharpe_ratio": 0,
        "max_win_streak": 0, "max_lose_streak": 0, "avg_pnl": 0,
    }


# ═══════════════════════════════════════════════
#  FORMATLAMA YARDIMCILARI
# ═══════════════════════════════════════════════

def format_pnl(pnl: float, show_pct: float = None) -> str:
    """P&L değerini emoji ile formatlar."""
    sign = "+" if pnl >= 0 else ""
    emoji = "💰" if pnl > 0 else "🔴" if pnl < 0 else "➡️"
    result = f"{emoji} {sign}${pnl:,.2f}"
    if show_pct is not None:
        result += f" ({sign}{show_pct:.2f}%)"
    return result


def format_leverage_impact(price: float, leverage: int,
                            price_move_pct: float = 1.0) -> str:
    """Kaldıraç etkisini açıklar."""
    impact = price_move_pct * leverage
    return (
        f"Fiyat %{price_move_pct} değişirse:\n"
        f"  {leverage}x kaldıraç → %{impact:.1f} etki\n"
        f"  $100 marjin üzerinde: {'+' if impact>0 else ''}"
        f"${impact:.2f}"
    )
