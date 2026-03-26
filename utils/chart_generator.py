"""
utils/chart_generator.py — Sinyal Grafiği + Kalite Skoru

Her sinyal için:
1. Mum grafiği (son 80 mum, 1h)
2. Giriş zonu (yeşil/kırmızı kutu)
3. TP1/TP2/TP3 çizgileri
4. Stop Loss çizgisi
5. FVG bölgesi (varsa)
6. MSB seviyesi (varsa)
7. EMA 20/50
8. Kalite skoru: A++/A+/A/B + açıklama
"""

import os
import logging
import numpy as np
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

CHARTS_DIR = "temp_charts"
os.makedirs(CHARTS_DIR, exist_ok=True)


# ─── KALİTE SKORU ────────────────────────────────────────────────────────────

def calculate_quality_score(signal: dict) -> dict:
    """
    Sinyal kalitesini 0-100 arasında puanlar, harf notu verir.
    """
    score = 0
    reasons = []
    warnings = []

    conf      = signal.get("confidence", 0)
    direction = signal.get("direction", "")
    sig_type  = signal.get("type", "NORMAL")
    bias      = signal.get("bias", {}) or {}
    rr        = float(signal.get("rr_ratio", 0) or 0)
    session   = signal.get("session", "")
    has_smt   = signal.get("has_smt", False)
    kill_zone = signal.get("kill_zone")

    # ── Güven skoru (max 25p) ─────────────────────────────────────────
    if conf >= 95:   score += 25; reasons.append("Çok yüksek güven (%{:.0f})".format(conf))
    elif conf >= 90: score += 20; reasons.append("Yüksek güven (%{:.0f})".format(conf))
    elif conf >= 85: score += 15; reasons.append("İyi güven (%{:.0f})".format(conf))
    elif conf >= 80: score += 10
    else:            score += 5;  warnings.append("Düşük güven (%{:.0f})".format(conf))

    # ── Bias gücü (max 20p) ───────────────────────────────────────────
    bias_str = float(bias.get("strength", 0) or 0)
    bias_zone = bias.get("zone", "") or ""
    if bias_str >= 0.7:  score += 20; reasons.append("Güçlü bias ({})".format(bias_zone))
    elif bias_str >= 0.5: score += 15; reasons.append("Orta bias ({})".format(bias_zone))
    elif bias_str >= 0.3: score += 8
    else:                 warnings.append("Zayıf bias")

    # ── PD Zone uyumu (max 15p) ───────────────────────────────────────
    dir_up  = direction.upper()
    zone_up = bias_zone.upper()
    if dir_up == "LONG"  and zone_up == "DISCOUNT": score += 15; reasons.append("DISCOUNT'ta LONG ✓")
    elif dir_up == "SHORT" and zone_up == "PREMIUM": score += 15; reasons.append("PREMIUM'da SHORT ✓")
    elif zone_up == "":  pass   # Zone bilgisi yoksa uyarı verme
    else: warnings.append("PD Zone uyumsuzluğu ({})".format(bias_zone))

    # ── R/R oranı (max 15p) ───────────────────────────────────────────
    if rr >= 3:    score += 15; reasons.append("Mükemmel R/R (1:{:.1f})".format(rr))
    elif rr >= 2:  score += 10; reasons.append("İyi R/R (1:{:.1f})".format(rr))
    elif rr >= 1.5: score += 5
    else:          warnings.append("Düşük R/R (1:{:.1f})".format(rr))

    # ── Seans kalitesi (max 10p) ──────────────────────────────────────
    if "Overlap" in session:   score += 10; reasons.append("Overlap seansı (en güçlü)")
    elif "Kill Zone" in session or kill_zone: score += 7; reasons.append("Kill Zone aktif")
    elif "Londra" in session or "New York" in session: score += 4
    else: warnings.append("Zayıf seans")

    # ── Sinyal tipi bonusu (max 10p) ──────────────────────────────────
    if sig_type == "CRT":     score += 10; reasons.append("A++ CRT yapısı")
    elif sig_type == "MSB_FVG": score += 7; reasons.append("MSB+FVG yapısı")
    else:                       score += 3

    # ── SMT bonusu (max 5p) ───────────────────────────────────────────
    if has_smt: score += 5; reasons.append("SMT uyumsuzluğu (tuz-biber)")

    # ── Harf notu ─────────────────────────────────────────────────────
    score = min(score, 100)
    if score >= 85:   grade = "A++"
    elif score >= 70: grade = "A+"
    elif score >= 55: grade = "A"
    else:             grade = "B"

    grade_emoji = {"A++": "🏆", "A+": "⭐⭐", "A": "⭐", "B": "📊"}

    return {
        "score":   score,
        "grade":   grade,
        "emoji":   grade_emoji[grade],
        "reasons": reasons,
        "warnings": warnings,
    }


def format_quality_block(signal: dict) -> str:
    """Telegram mesajına eklenecek kalite bloğu."""
    q = calculate_quality_score(signal)
    bar_filled = int(q["score"] / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    lines = [
        f"\n{'─'*32}",
        f"{q['emoji']} **Sinyal Kalitesi: {q['grade']}** ({q['score']}/100)",
        f"`{bar}`",
    ]
    if q["reasons"]:
        lines.append("✅ " + " | ".join(q["reasons"][:3]))
    if q["warnings"]:
        lines.append("⚠️ " + " | ".join(q["warnings"][:2]))

    return "\n".join(lines)


# ─── GRAFİK ──────────────────────────────────────────────────────────────────

def _fmt_price(price: float) -> str:
    """Grafik için fiyat formatı."""
    if price == 0: return "0"
    elif price < 0.0001: return f"{price:.8f}"
    elif price < 0.01: return f"{price:.6f}"
    elif price < 1: return f"{price:.4f}"
    elif price < 100: return f"{price:.4f}"
    else: return f"{price:,.2f}"


def generate_signal_chart(signal: dict) -> Optional[str]:
    """
    Sinyal için mum grafiği oluşturur.
    Giriş zonu, TP'ler, SL, FVG, MSB, EMA çizer.
    PNG dosya yolunu döner.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyArrowPatch

        from utils.market_data import get_klines
        from utils.technical_analysis import (
            calculate_ema, detect_fvg, detect_msb, determine_bias
        )

        pair     = signal.get("pair", "BTCUSDT")
        raw_tf = signal.get("timeframe", "1h")
        sig_type_tf = signal.get("type", "NORMAL")

        # Her sinyal kendi timeframe'inde gösterilir
        if sig_type_tf == "CRT_1D":
            tf = "1d"
        elif sig_type_tf == "CRT":
            tf = "4h"
        else:
            # NORMAL ve MSB_FVG — hangi TF'de bulunduysa onu kullan
            tf = raw_tf.split()[0].lower()
            # "4H → 1H Onayı" gibi formatları temizle
            tf = tf.replace("→", "").strip()
            if tf not in ("1h", "4h", "15m", "1d", "4h"):
                tf = "1h"  # bilinmeyen format → 1H

        candles = get_klines(pair, tf, limit=80)
        if not candles or len(candles) < 20:
            return None

        closes = np.array([c["close"] for c in candles])
        opens  = np.array([c["open"]  for c in candles])
        highs  = np.array([c["high"]  for c in candles])
        lows   = np.array([c["low"]   for c in candles])
        times  = list(range(len(candles)))

        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)

        direction  = signal.get("direction", "LONG")
        entry_min  = signal.get("entry_min", closes[-1])
        entry_max  = signal.get("entry_max", closes[-1])
        stop_loss  = signal.get("stop_loss", 0)
        tp1        = signal.get("tp1", 0)
        tp2        = signal.get("tp2", 0)
        tp3        = signal.get("tp3", 0)

        # Kalite skoru
        q = calculate_quality_score(signal)

        # ── FIGURE ────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 8))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")

        # ── MUM GRAFİĞİ ───────────────────────────────────────────────
        for i in range(len(candles)):
            color = "#26a69a" if closes[i] >= opens[i] else "#ef5350"
            # Gövde
            ax.bar(i, abs(closes[i] - opens[i]),
                   bottom=min(opens[i], closes[i]),
                   color=color, width=0.6, alpha=0.9)
            # İğne
            ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.8, alpha=0.7)

        # ── EMA ───────────────────────────────────────────────────────
        valid20 = ~np.isnan(ema20)
        valid50 = ~np.isnan(ema50)
        if valid20.any():
            ax.plot(np.array(times)[valid20], ema20[valid20],
                    color="#29b6f6", linewidth=1.2, alpha=0.8, label="EMA 20", zorder=3)
        if valid50.any():
            ax.plot(np.array(times)[valid50], ema50[valid50],
                    color="#ff9800", linewidth=1.2, alpha=0.8, label="EMA 50", zorder=3)

        # ── FVG BÖLGELERİ ─────────────────────────────────────────────
        try:
            fvgs = detect_fvg(candles)
            fvg_yon = "BULLISH" if direction == "LONG" else "BEARISH"
            for fvg in [f for f in fvgs[:3] if f["type"] == fvg_yon and not f["filled"]]:
                ax.axhspan(fvg["bottom"], fvg["top"],
                           color="#ffd700", alpha=0.08, zorder=1)
                ax.axhline(fvg["midpoint"], color="#ffd700",
                           linewidth=0.8, linestyle=":", alpha=0.5)
                ax.text(2, fvg["midpoint"], "CE",
                        color="#ffd700", fontsize=7, alpha=0.7, va="center")
        except:
            pass

        # ── GİRİŞ ZONU ────────────────────────────────────────────────
        zone_color = "#26a69a" if direction == "LONG" else "#ef5350"
        ax.axhspan(entry_min, entry_max, color=zone_color, alpha=0.15, zorder=2)
        ax.axhline((entry_min + entry_max) / 2,
                   color=zone_color, linewidth=1.5, linestyle="--", alpha=0.8, zorder=3)

        # ── SİNYAL ANI FİYATI ─────────────────────────────────────────
        current_price = signal.get("current_price", 0)
        if current_price:
            ax.axhline(current_price, color="#ffffff", linewidth=1.0,
                       linestyle=":", alpha=0.6, zorder=3)
            ax.text(1, current_price, f" Sinyal: ${_fmt_price(current_price)}",
                    color="#ffffff", fontsize=7, va="bottom", alpha=0.7)

        # ── STOP LOSS ─────────────────────────────────────────────────
        ax.axhline(stop_loss, color="#ff1744", linewidth=1.5,
                   linestyle="--", alpha=0.9, zorder=3)
        ax.text(len(candles) - 1, stop_loss, " SL",
                color="#ff1744", fontsize=8, va="center", fontweight="bold")

        # ── HEDEFLER ──────────────────────────────────────────────────
        tp_colors = ["#69f0ae", "#00e676", "#00c853"]
        for tp_val, tp_label, tp_color in [
            (tp1, "TP1", tp_colors[0]),
            (tp2, "TP2", tp_colors[1]),
            (tp3, "TP3", tp_colors[2]),
        ]:
            if tp_val:
                ax.axhline(tp_val, color=tp_color, linewidth=1.2,
                           linestyle="-.", alpha=0.8, zorder=3)
                ax.text(len(candles) - 1, tp_val, f" {tp_label}",
                        color=tp_color, fontsize=8, va="center", fontweight="bold")

        # ── MSB SEVİYESİ ──────────────────────────────────────────────
        try:
            msb_dir = "long" if direction == "LONG" else "short"
            msb = detect_msb(candles, msb_dir)
            if msb["detected"] and msb.get("level"):
                ax.axhline(msb["level"], color="#ce93d8", linewidth=1.0,
                           linestyle=":", alpha=0.7, zorder=3)
                ax.text(2, msb["level"], f"MSB ({msb['strength']})",
                        color="#ce93d8", fontsize=7, alpha=0.8, va="bottom")
        except:
            pass

        # ── OK İŞARETİ (Giriş noktası) ────────────────────────────────
        arrow_y = entry_max if direction == "LONG" else entry_min
        arrow_dy = (tp1 - entry_max) * 0.3 if direction == "LONG" else (entry_min - tp1) * 0.3
        ax.annotate("",
            xy=(len(candles) - 2, arrow_y + arrow_dy),
            xytext=(len(candles) - 2, arrow_y),
            arrowprops=dict(arrowstyle="->", color=zone_color, lw=2.0)
        )

        # ── BAŞLIK ────────────────────────────────────────────────────
        pair_label = pair.replace("USDT", "/USDT")
        sig_type   = signal.get("type", "NORMAL")
        sess       = signal.get("session", "")
        created    = signal.get("created_at", "")

        grade_color = {"A++": "#ffd700", "A+": "#69f0ae", "A": "#29b6f6", "B": "#ffffff"}
        gc = grade_color.get(q["grade"], "#ffffff")

        ax.set_title(
            f"{pair_label}  |  {sig_type}  |  {direction}  |  {tf.upper()}  |  {created}",
            color="white", fontsize=12, pad=10, loc="left"
        )

        # Kalite bandı — sağ üst
        ax.text(0.99, 0.97,
                f"{q['emoji']} {q['grade']}  {q['score']}/100",
                transform=ax.transAxes, color=gc, fontsize=13,
                fontweight="bold", ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#1a1a2e", alpha=0.8))

        # Neden işleme giriyoruz — alt açıklama
        reasons_text = "  •  ".join(q["reasons"][:4]) if q["reasons"] else ""
        if q["warnings"]:
            reasons_text += "   ⚠️ " + " | ".join(q["warnings"][:2])

        fig.text(0.01, 0.01, reasons_text,
                 color="#aaaaaa", fontsize=8, ha="left", va="bottom",
                 style="italic")

        # Seans etiketi
        ax.text(0.01, 0.97, f"🕐 {sess}",
                transform=ax.transAxes, color="#ffd700",
                fontsize=9, ha="left", va="top", alpha=0.9)

        # ── EKSENLERİ DÜZENLE ─────────────────────────────────────────
        ax.tick_params(colors="#888888", labelsize=8)
        ax.spines["bottom"].set_color("#333333")
        ax.spines["left"].set_color("#333333")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.yaxis.set_label_position("right")
        ax.yaxis.tick_right()
        ax.grid(True, alpha=0.06, color="#ffffff")
        ax.legend(loc="upper left", fontsize=8,
                  facecolor="#1a1a2e", edgecolor="#333333",
                  labelcolor="white", framealpha=0.8)

        # Y eksen aralığı — SL ve TP3 arasını göster
        all_levels = [l for l in [stop_loss, tp3, entry_min, entry_max] if l]
        if all_levels:
            margin = (max(all_levels) - min(all_levels)) * 0.15
            ax.set_ylim(min(all_levels) - margin, max(all_levels) + margin)

        # ── KAYDET ────────────────────────────────────────────────────
        fname = f"{CHARTS_DIR}/{pair}_{sig_type}_{datetime.now().strftime('%H%M%S')}.png"
        plt.savefig(fname, dpi=130, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return fname

    except Exception as e:
        logger.error(f"Grafik oluşturma hatası ({signal.get('pair','?')}): {e}")
        return None
