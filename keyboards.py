"""
╔══════════════════════════════════════════════════════════════╗
║    DOSYA 7: keyboards.py — Tüm Telegram Inline Klavyeleri    ║
╚══════════════════════════════════════════════════════════════╝

Bu dosya: Botun tüm inline klavyelerini ve butonlarını
merkezi olarak tanımlar. Her handler bu dosyayı import
eder. Bu yaklaşım, buton değişikliklerini tek yerden
yönetmeyi sağlar.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SUPPORTED_PAIRS, LEVERAGE_OPTIONS, TIMEFRAMES


# ═══════════════════════════════════════════════
#  ANA MENÜ
# ═══════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Ana menü butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Normal Sinyaller",  callback_data="menu_signals"),
            InlineKeyboardButton("🎯 MSB+FVG",           callback_data="menu_msb_fvg"),
        ],
        [
            InlineKeyboardButton("🔷 CRT Analizi",       callback_data="menu_crt"),
            InlineKeyboardButton("🔥 Likidite",          callback_data="menu_liquidity"),
        ],
        [
            InlineKeyboardButton("💼 Pozisyonlarım",     callback_data="menu_positions"),
            InlineKeyboardButton("📊 Kar/Zarar",         callback_data="menu_pnl"),
        ],
        [
            InlineKeyboardButton("🤖 AI Coach",          callback_data="menu_ai_coach"),
            InlineKeyboardButton("📈 Backtesting",       callback_data="menu_backtest"),
        ],
        [
            InlineKeyboardButton("📉 Piyasa Özeti",      callback_data="menu_market"),
            InlineKeyboardButton("⚙️ Ayarlar",           callback_data="menu_settings"),
        ],
    ])


# ═══════════════════════════════════════════════
#  SİNYAL MENÜSü
# ═══════════════════════════════════════════════

def signals_menu_keyboard() -> InlineKeyboardMarkup:
    """Normal sinyaller menüsü."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔔 Yeni Sinyal Tara",   callback_data="signal_scan"),
            InlineKeyboardButton("📋 Son Sinyaller",       callback_data="signal_list"),
        ],
        [
            InlineKeyboardButton("⭐ BTC/USDT",            callback_data="signal_pair_BTCUSDT"),
            InlineKeyboardButton("⭐ ETH/USDT",            callback_data="signal_pair_ETHUSDT"),
        ],
        [
            InlineKeyboardButton("SOL/USDT",               callback_data="signal_pair_SOLUSDT"),
            InlineKeyboardButton("BNB/USDT",               callback_data="signal_pair_BNBUSDT"),
        ],
        [
            InlineKeyboardButton("📊 Tüm Coinleri Tara",  callback_data="signal_scan_all"),
        ],
        [InlineKeyboardButton("◀️ Ana Menü",               callback_data="menu_main")],
    ])


def signal_detail_keyboard(signal_id: int, pair: str) -> InlineKeyboardMarkup:
    """Tek sinyal detay sayfası butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💼 Pozisyon Aç",        callback_data=f"pos_open_{signal_id}"),
            InlineKeyboardButton("⭐ Favorile",            callback_data=f"signal_fav_{signal_id}"),
        ],
        [
            InlineKeyboardButton("📊 Grafik Analiz",      callback_data=f"signal_chart_{pair}"),
            InlineKeyboardButton("🔄 Yenile",              callback_data=f"signal_refresh_{signal_id}"),
        ],
        [InlineKeyboardButton("🔔 Fiyat Alarmı Kur",     callback_data=f"alarm_set_{signal_id}_{pair}")],
        [InlineKeyboardButton("◀️ Sinyaller",             callback_data="menu_signals")],
    ])


# ═══════════════════════════════════════════════
#  POZİSYON MENÜSÜ
# ═══════════════════════════════════════════════

def positions_menu_keyboard() -> InlineKeyboardMarkup:
    """Aktif pozisyonlar menüsü."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tüm Pozisyonlar",    callback_data="pos_list"),
            InlineKeyboardButton("➕ Yeni Pozisyon",       callback_data="pos_new"),
        ],
        [
            InlineKeyboardButton("🔄 Fiyatları Güncelle", callback_data="pos_refresh"),
            InlineKeyboardButton("📊 Özet Rapor",         callback_data="pos_summary"),
        ],
        [InlineKeyboardButton("◀️ Ana Menü",               callback_data="menu_main")],
    ])


def position_detail_keyboard(position_id: int) -> InlineKeyboardMarkup:
    """Tek pozisyon detay sayfası butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Tümünü Kapat",        callback_data=f"pos_close_{position_id}"),
            InlineKeyboardButton("✂️ Kısmi Kapat",         callback_data=f"pos_partial_{position_id}"),
        ],
        [
            InlineKeyboardButton("🎯 SL/TP Düzenle",      callback_data=f"pos_edit_{position_id}"),
            InlineKeyboardButton("🔄 Yenile",              callback_data=f"pos_refresh_{position_id}"),
        ],
        [InlineKeyboardButton("◀️ Pozisyonlar",           callback_data="pos_list")],
    ])


def close_position_confirm_keyboard(position_id: int) -> InlineKeyboardMarkup:
    """Pozisyon kapatma onay butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ EVET, Kapat",         callback_data=f"pos_close_confirm_{position_id}"),
            InlineKeyboardButton("❌ İptal",               callback_data=f"pos_detail_{position_id}"),
        ],
    ])


def partial_close_keyboard(position_id: int) -> InlineKeyboardMarkup:
    """Kısmi kapatma yüzde butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("25%",  callback_data=f"pos_partial_25_{position_id}"),
            InlineKeyboardButton("50%",  callback_data=f"pos_partial_50_{position_id}"),
            InlineKeyboardButton("75%",  callback_data=f"pos_partial_75_{position_id}"),
        ],
        [InlineKeyboardButton("◀️ İptal", callback_data=f"pos_detail_{position_id}")],
    ])


def tp_action_keyboard(position_id: int, tp_level: int) -> InlineKeyboardMarkup:
    """TP ulaşıldığında gösterilen aksiyon butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ %{30 if tp_level==1 else 40 if tp_level==2 else 30}'ını Kapat",
                callback_data=f"tp_close_partial_{position_id}_{tp_level}"
            ),
        ],
        [
            InlineKeyboardButton("💯 Tümünü Kapat",       callback_data=f"pos_close_{position_id}"),
            InlineKeyboardButton("▶️ Devam Et",            callback_data=f"tp_continue_{position_id}"),
        ],
    ])


# ═══════════════════════════════════════════════
#  YENİ POZİSYON AÇMA FORMU
# ═══════════════════════════════════════════════

def direction_keyboard() -> InlineKeyboardMarkup:
    """Long/Short seçimi."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 LONG  (Alış)",       callback_data="new_pos_LONG"),
            InlineKeyboardButton("📉 SHORT (Satış)",      callback_data="new_pos_SHORT"),
        ],
        [InlineKeyboardButton("◀️ İptal",                callback_data="menu_positions")],
    ])


def pair_select_keyboard(callback_prefix: str = "new_pos_pair") -> InlineKeyboardMarkup:
    """Coin çifti seçim klavyesi."""
    buttons = []
    row = []
    for i, pair in enumerate(SUPPORTED_PAIRS[:8]):
        label = pair.replace("USDT", "")
        row.append(InlineKeyboardButton(label, callback_data=f"{callback_prefix}_{pair}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ İptal", callback_data="menu_positions")])
    return InlineKeyboardMarkup(buttons)


def leverage_keyboard(callback_prefix: str = "new_pos_lev") -> InlineKeyboardMarkup:
    """Kaldıraç seçim klavyesi."""
    buttons = []
    row = []
    risk_colors = {1: "🟢", 2: "🟢", 3: "🟡", 5: "🟡", 10: "🟠", 20: "🔴", 50: "🔴", 100: "💀"}
    for lev in LEVERAGE_OPTIONS:
        color = risk_colors.get(lev, "⚪")
        row.append(InlineKeyboardButton(f"{color}{lev}x", callback_data=f"{callback_prefix}_{lev}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ İptal", callback_data="menu_positions")])
    return InlineKeyboardMarkup(buttons)


def margin_keyboard(callback_prefix: str = "new_pos_margin") -> InlineKeyboardMarkup:
    """Marjin miktarı seçim klavyesi."""
    amounts = [20, 50, 100, 200, 500]
    buttons = []
    row = []
    for amount in amounts:
        row.append(InlineKeyboardButton(f"${amount}", callback_data=f"{callback_prefix}_{amount}"))
    buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ Özel Tutar Gir", callback_data=f"{callback_prefix}_custom")])
    buttons.append([InlineKeyboardButton("◀️ İptal",          callback_data="menu_positions")])
    return InlineKeyboardMarkup(buttons)


def confirm_position_keyboard(pos_data_key: str) -> InlineKeyboardMarkup:
    """Pozisyon onay butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ POZİSYONU AÇ",       callback_data=f"pos_confirm_{pos_data_key}"),
            InlineKeyboardButton("❌ İptal",               callback_data="menu_positions"),
        ],
    ])


# ═══════════════════════════════════════════════
#  P&L MENÜSÜ
# ═══════════════════════════════════════════════

def pnl_menu_keyboard() -> InlineKeyboardMarkup:
    """Kar/Zarar menüsü."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Bugün",              callback_data="pnl_period_1"),
            InlineKeyboardButton("📅 Bu Hafta",           callback_data="pnl_period_7"),
            InlineKeyboardButton("📅 Bu Ay",              callback_data="pnl_period_30"),
        ],
        [
            InlineKeyboardButton("📅 3 Ay",               callback_data="pnl_period_90"),
            InlineKeyboardButton("📅 1 Yıl",              callback_data="pnl_period_365"),
            InlineKeyboardButton("📅 Tümü",               callback_data="pnl_period_0"),
        ],
        [
            InlineKeyboardButton("📋 İşlem Geçmişi",      callback_data="pnl_history"),
            InlineKeyboardButton("📊 İstatistikler",      callback_data="pnl_stats"),
        ],
        [
            InlineKeyboardButton("🏆 En İyi/Kötü",        callback_data="pnl_best_worst"),
            InlineKeyboardButton("💹 Coin Analizi",       callback_data="pnl_by_coin"),
        ],
        [InlineKeyboardButton("◀️ Ana Menü",               callback_data="menu_main")],
    ])


# ═══════════════════════════════════════════════
#  AYARLAR MENÜSÜ
# ═══════════════════════════════════════════════

def settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Ayarlar menüsü."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔔 Bildirimler",        callback_data="settings_notifications"),
            InlineKeyboardButton("💰 Varsayılan Marjin",  callback_data="settings_margin"),
        ],
        [
            InlineKeyboardButton("⚡ Varsayılan Kaldıraç",callback_data="settings_leverage"),
            InlineKeyboardButton("🎯 Min. Güven Skoru",   callback_data="settings_confidence"),
        ],
        [
            InlineKeyboardButton("⚖️ Risk Profili",       callback_data="settings_risk"),
            InlineKeyboardButton("🔑 API Ayarları",       callback_data="settings_api"),
        ],
        [
            InlineKeyboardButton("🔄 Demo Hesabı Sıfırla",callback_data="settings_reset_balance"),
            InlineKeyboardButton("🗑️ TÜM VERİ SİL",      callback_data="settings_reset_all"),
        ],
        [InlineKeyboardButton("◀️ Ana Menü",               callback_data="menu_main")],
    ])


def confirm_reset_keyboard(reset_type: str) -> InlineKeyboardMarkup:
    """Sıfırlama onay butonları."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ EVET, SİL",          callback_data=f"reset_confirm_{reset_type}"),
            InlineKeyboardButton("❌ İptal",               callback_data="menu_settings"),
        ],
    ])


def risk_level_keyboard() -> InlineKeyboardMarkup:
    """Risk profili seçimi."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Muhafazakâr",            callback_data="settings_risk_LOW")],
        [InlineKeyboardButton("🟡 Dengeli",                callback_data="settings_risk_MEDIUM")],
        [InlineKeyboardButton("🔴 Agresif",                callback_data="settings_risk_HIGH")],
        [InlineKeyboardButton("◀️ Ayarlar",                callback_data="menu_settings")],
    ])


# ═══════════════════════════════════════════════
#  GENEL YARDIMCI BUTONLAR
# ═══════════════════════════════════════════════

def back_to_main() -> InlineKeyboardMarkup:
    """Sadece 'Ana Menüye Dön' butonu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Ana Menü", callback_data="menu_main")]
    ])


def back_button(callback: str, label: str = "◀️ Geri") -> InlineKeyboardMarkup:
    """Tek geri butonu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=callback)]
    ])


def timeframe_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """Timeframe seçim klavyesi."""
    tfs = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    row = [InlineKeyboardButton(t.upper(), callback_data=f"{callback_prefix}_{t}") for t in tfs]
    return InlineKeyboardMarkup([row[:4], row[4:],
                                  [InlineKeyboardButton("◀️ İptal", callback_data="menu_main")]])


def yes_no_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    """Basit Evet/Hayır butonu."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Evet", callback_data=yes_cb),
            InlineKeyboardButton("❌ Hayır", callback_data=no_cb),
        ]
    ])
