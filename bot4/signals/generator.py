"""
bot4/signals/generator.py
A++ Setup Motoru - Asakura egitiminin tam kural seti.

DEGISIKLIKLER (onceki versiyona gore):
  - Skor max 10 -> max 12
  - Seans kalitesi: sadece kill_zone degil, Overlap +1, KZ +0.5
  - Judas Swing yon uyumu: +1
  - Spooling penceresi/mumu: +0.5
  - Karakter Degisimi (ChoCH): +1
  - CE yakinligi: +0.5
  - Grade esikleri: A++=9+, A+=7+, A=5+, B<5
  - Pazartesi filtresi: islem yok (Fog of War)
  - TGIF: Cuma bayragi
  - TP1'de riski sifirla: not eklendi
"""

from indicators.market_structure import (
    find_swing_points, detect_msb, detect_bos, determine_trend
)
from indicators.fvg import find_fvg, find_fvg_near_msb
from indicators.crt import detect_crt, detect_ce_levels
from indicators.order_blocks import find_nearest_ob, is_price_in_ob
from indicators.smt import detect_smt_divergence
from indicators.liquidity import find_liquidity_pools, detect_stop_hunt
from indicators.ote import calculate_ote_zone
from utils.helpers import (
    is_kill_zone, get_current_session, get_session_quality,
    calculate_rr_ratio, calculate_premium_discount,
    format_price, is_friday_tgif, is_monday,
    is_spooling_window, is_overlap_session,
)


class SignalGenerator:

    def __init__(self):
        self.min_score = 5   # Grade A minimum

    def analyze_coin(self, symbol, data_by_tf, data_correlated=None):
        """
        Bir coini tum timeframe'lerde analiz et.
        data_by_tf: {'1d': df, '4h': df, '1h': df, '15m': df}
        """
        required = ['1d', '4h', '1h', '15m']
        for tf in required:
            if tf not in data_by_tf or data_by_tf[tf] is None or len(data_by_tf[tf]) < 30:
                return None

        # Pazartesi: Fog of War
        if is_monday():
            return None

        # ── Adım 1: HTF Bias ────────────────────────────────
        htf_bias = self._analyze_htf_bias(data_by_tf['1d'])
        if not htf_bias:
            return None

        # ── Adım 2: CRT (1D / 4H) ───────────────────────────
        crt_1d = detect_crt(data_by_tf['1d'], direction=htf_bias['direction'])
        crt_4h = detect_crt(data_by_tf['4h'], direction=htf_bias['direction'])
        crt       = crt_1d or crt_4h
        crt_found = crt is not None

        # Karakter Degisimi (CRT icerisinde)
        choch_confirmed = False
        if crt and crt.get('character_change', {}).get('confirmed'):
            choch_confirmed = True

        # ── Adım 3: 4H Trend ────────────────────────────────
        trend_4h      = determine_trend(data_by_tf['4h'])
        trend_aligned = (
            (htf_bias['direction'] == 'short' and trend_4h == 'bearish') or
            (htf_bias['direction'] == 'long'  and trend_4h == 'bullish')
        )

        # ── Adım 4: MSB (1H) ────────────────────────────────
        msb_1h = detect_msb(data_by_tf['1h'], htf_bias['direction'])
        if not msb_1h:
            return None

        # ── Adım 5: FVG (15M) ───────────────────────────────
        fvg_15m = find_fvg_near_msb(
            data_by_tf['15m'],
            msb_price  = msb_1h['broken_level'],
            direction  = htf_bias['direction']
        )
        if not fvg_15m:
            fvg_15m = find_fvg(data_by_tf['15m'], htf_bias['direction'])

        # ── Adım 6: Order Block ──────────────────────────────
        ob = find_nearest_ob(data_by_tf['1h'], htf_bias['direction'])

        # ── Adım 7: SMT ─────────────────────────────────────
        smt = None
        if data_correlated:
            tf_corr = data_correlated.get('4h')
            tf_main = data_by_tf.get('4h')
            if tf_corr is not None and tf_main is not None:
                smt = detect_smt_divergence(tf_main, tf_corr)
                if smt and smt['direction'] != htf_bias['direction']:
                    smt = None

        # ── Adım 8: Likidite Hedefleri ───────────────────────
        liquidity_targets = find_liquidity_pools(
            data_by_tf['4h'], htf_bias['direction']
        )

        # ── Adım 9: Stop Hunt ────────────────────────────────
        stop_hunt = detect_stop_hunt(data_by_tf['15m'])

        # ── Adım 10: Seans ──────────────────────────────────
        kill_zone      = is_kill_zone()
        session        = get_current_session()
        session_quality = get_session_quality()    # 0-3
        overlap        = is_overlap_session()
        spooling, sp_name = is_spooling_window()

        # ── Adım 11: OTE Bolgesi ─────────────────────────────
        ote = calculate_ote_zone(
            htf_bias['swing_low'],
            htf_bias['swing_high'],
            htf_bias['direction']
        )
        current_price = float(data_by_tf['1h']['close'].iloc[-1])
        in_ote_zone   = ote['zone_low'] <= current_price <= ote['zone_high']

        # ── Adım 12: CE Seviyeleri ────────────────────────────
        ce_levels     = detect_ce_levels(data_by_tf['15m'])
        ce_proximity  = self._ce_proximity(ce_levels, current_price,
                                           htf_bias['direction'])

        # ── Adım 13: Judas Swing ─────────────────────────────
        judas_aligned = False
        judas_detail  = None
        try:
            from utils.helpers import check_judas_swing
            judas_detail  = check_judas_swing(data_by_tf.get('1m'), htf_bias['direction'])
            judas_aligned = judas_detail is not None and judas_detail.get('aligned', False)
        except:
            pass

        # ── Adım 14: Skor Hesapla ────────────────────────────
        score, breakdown = self._calculate_score(
            htf_bias        = htf_bias,
            crt_found       = crt_found,
            choch_confirmed = choch_confirmed,
            trend_aligned   = trend_aligned,
            msb             = msb_1h,
            fvg             = fvg_15m,
            ob              = ob,
            smt             = smt,
            kill_zone       = kill_zone,
            in_ote_zone     = in_ote_zone,
            stop_hunt       = stop_hunt,
            session_quality = session_quality,
            judas_aligned   = judas_aligned,
            spooling        = spooling,
            ce_proximity    = ce_proximity,
        )

        if score < self.min_score:
            return None

        # ── Adım 15: Entry/SL/TP ─────────────────────────────
        entry_data = self._calculate_entry_stop_tp(
            htf_bias          = htf_bias,
            msb               = msb_1h,
            fvg               = fvg_15m,
            ob                = ob,
            ote               = ote,
            liquidity_targets = liquidity_targets,
            current_price     = current_price
        )
        if not entry_data:
            return None

        # ── Adım 16: Sinyal Olustur ───────────────────────────
        return self._create_signal(
            symbol         = symbol,
            score          = score,
            breakdown      = breakdown,
            htf_bias       = htf_bias,
            crt            = crt,
            msb            = msb_1h,
            fvg            = fvg_15m,
            ob             = ob,
            smt            = smt,
            entry_data     = entry_data,
            session        = session,
            session_quality = session_quality,
            kill_zone      = kill_zone,
            judas_aligned  = judas_aligned,
            spooling       = spooling,
            sp_name        = sp_name,
            choch_confirmed = choch_confirmed,
            ce_proximity   = ce_proximity,
        )

    # ─────────────────────────────────────────────────────────

    def _analyze_htf_bias(self, data_1d):
        if len(data_1d) < 30:
            return None
        swing_highs, swing_lows = find_swing_points(data_1d, lookback=5)
        if not swing_highs or not swing_lows:
            return None

        recent_high   = swing_highs[-1]['price']
        recent_low    = swing_lows[-1]['price']
        current_price = float(data_1d['close'].iloc[-1])
        pd_info       = calculate_premium_discount(current_price, recent_high, recent_low)
        trend         = determine_trend(data_1d, lookback=5)

        # Egitim kurali: Trend + PD uyumu zorunlu
        if trend == 'bearish' and pd_info['zone'] == 'PREMIUM':
            direction = 'short'
        elif trend == 'bullish' and pd_info['zone'] == 'DISCOUNT':
            direction = 'long'
        else:
            return None   # Uyumsuz — A++ olmaz

        if pd_info['strength'] < 0.2:
            return None   # Cok zayif

        return {
            'direction':   direction,
            'trend':       trend,
            'zone':        pd_info['zone'],
            'strength':    pd_info['strength'],
            'swing_high':  recent_high,
            'swing_low':   recent_low,
            'fib_50':      pd_info['fib_50'],
            'fib_62':      pd_info.get('fib_62', recent_high - (recent_high-recent_low)*0.618),
            'fib_705':     pd_info.get('fib_705', recent_high - (recent_high-recent_low)*0.705),
            'fib_79':      pd_info.get('fib_79',  recent_high - (recent_high-recent_low)*0.790),
            'current_price': current_price,
        }

    def _ce_proximity(self, ce_levels, price, direction) -> bool:
        """Fiyat CE noktasina %0.5 icinde mi?"""
        if not ce_levels:
            return False
        for ce in ce_levels:
            if abs(ce - price) / price < 0.005:
                return True
        return False

    def _calculate_score(self, htf_bias, crt_found, choch_confirmed,
                         trend_aligned, msb, fvg, ob, smt,
                         kill_zone, in_ote_zone, stop_hunt,
                         session_quality, judas_aligned,
                         spooling, ce_proximity):
        """
        Egitim skoru — max 12 puan.
        Grade: A++=9+, A+=7+, A=5+, B<5
        """
        score     = 0.0
        breakdown = {}

        # 1. HTF Bias gucu (max 2)
        if htf_bias['strength'] > 0.7:
            score += 2
            breakdown['htf_bias'] = 'Guclu Bias (2p)'
        elif htf_bias['strength'] > 0.4:
            score += 1
            breakdown['htf_bias'] = 'Zayif Bias (1p)'

        # 2. 4H Trend uyumu (1)
        if trend_aligned:
            score += 1
            breakdown['trend'] = '4H Trend Uyumlu (1p)'

        # 3. CRT yapisi (2)
        if crt_found:
            score += 2
            breakdown['crt'] = 'CRT Aktif (2p)'

        # 4. Karakter Degisimi / ChoCH (1) — YENI
        if choch_confirmed:
            score += 1
            breakdown['choch'] = 'Karakter Degisimi (1p)'

        # 5. MSB (2) — zorunlu (zaten filtre)
        if msb:
            score += 2
            breakdown['msb'] = f"MSB: {msb.get('type','?')} (2p)"

        # 6. FVG (1)
        if fvg:
            score += 1
            breakdown['fvg'] = f"FVG: {fvg.get('type','?')} (1p)"

        # 7. Order Block (0.5)
        if ob:
            score += 0.5
            breakdown['ob'] = f"OB: {ob.get('type','?')} (0.5p)"

        # 8. SMT (2) — tuz biber
        if smt:
            score += 2
            breakdown['smt'] = f"SMT: {smt.get('type','?')} (2p)"

        # 9. OTE bolgesi (0.5)
        if in_ote_zone:
            score += 0.5
            breakdown['ote'] = 'OTE Bolgesinde (0.5p)'

        # 10. Seans kalitesi — YENI (Overlap bonus)
        if session_quality == 3:
            score += 1
            breakdown['session'] = 'Overlap Seasi (1p)'
        elif kill_zone:
            score += 0.5
            breakdown['session'] = 'Kill Zone (0.5p)'

        # 11. Judas Swing yon uyumu — YENI (1)
        if judas_aligned:
            score += 1
            breakdown['judas'] = 'Judas Swing Uyumlu (1p)'

        # 12. Spooling penceresi — YENI (0.5)
        if spooling:
            score += 0.5
            breakdown['spooling'] = 'Spooling Penceresi (0.5p)'

        # 13. CE yakinligi — YENI (0.5)
        if ce_proximity:
            score += 0.5
            breakdown['ce'] = 'CE Yakinligi (0.5p)'

        # 14. Stop Hunt (0.5)
        if stop_hunt:
            score += 0.5
            breakdown['stop_hunt'] = 'Stop Hunt (0.5p)'

        return round(score, 1), breakdown

    def _calculate_entry_stop_tp(self, htf_bias, msb, fvg, ob, ote,
                                  liquidity_targets, current_price):
        direction = htf_bias['direction']

        if fvg and not fvg.get('is_filled', False):
            entry_low  = fvg['bottom']
            entry_high = fvg['top']
        elif ob and is_price_in_ob(current_price, ob, tolerance=0.02):
            entry_low  = ob['bottom']
            entry_high = ob['top']
        else:
            entry_low  = ote['zone_low']
            entry_high = ote['zone_high']

        if entry_low >= entry_high:
            spread     = current_price * 0.003
            entry_low  = current_price - spread
            entry_high = current_price + spread

        optimal = (entry_low + entry_high) / 2

        if direction == 'short':
            sl    = msb['swing_high'] * 1.005
        else:
            sl    = msb['swing_low']  * 0.995

        risk_pct = abs(optimal - sl) / optimal
        if risk_pct > 0.15 or risk_pct < 0.001:
            return None

        risk = abs(optimal - sl)

        if direction == 'short':
            tp1 = optimal - risk * 1.5
            tp2 = optimal - risk * 2.5
            tp3 = optimal - risk * 4.0
            if liquidity_targets:
                lt = liquidity_targets[0]['level']
                if lt < optimal:
                    tp3 = lt
            tp3 = min(tp3, htf_bias['swing_low'])
        else:
            tp1 = optimal + risk * 1.5
            tp2 = optimal + risk * 2.5
            tp3 = optimal + risk * 4.0
            if liquidity_targets:
                lt = liquidity_targets[0]['level']
                if lt > optimal:
                    tp3 = lt
            tp3 = max(tp3, htf_bias['swing_high'])

        return {
            'entry_low':      round(entry_low, 6),
            'entry_high':     round(entry_high, 6),
            'optimal_entry':  round(optimal, 6),
            'stop_loss':      round(sl, 6),
            'tp1':            round(tp1, 6),
            'tp2':            round(tp2, 6),
            'tp3':            round(tp3, 6),
            'risk_pct':       round(risk_pct * 100, 2),
        }

    def _create_signal(self, symbol, score, breakdown, htf_bias, crt, msb,
                       fvg, ob, smt, entry_data, session, session_quality,
                       kill_zone, judas_aligned, spooling, sp_name,
                       choch_confirmed, ce_proximity):
        direction = htf_bias['direction']
        entry = entry_data['optimal_entry']
        sl    = entry_data['stop_loss']
        tp1, tp2, tp3 = entry_data['tp1'], entry_data['tp2'], entry_data['tp3']

        rr1 = calculate_rr_ratio(entry, sl, tp1)
        rr2 = calculate_rr_ratio(entry, sl, tp2)
        rr3 = calculate_rr_ratio(entry, sl, tp3)

        # Egitim grade esikleri (guncellendi)
        if score >= 9:   grade = 'A++'   # MAMACITA
        elif score >= 7: grade = 'A+'
        elif score >= 5: grade = 'A'
        else:            grade = 'B'

        is_friday = is_friday_tgif()

        return {
            'symbol':        symbol,
            'direction':     direction,
            'setup_grade':   grade,
            'score':         score,
            'is_mamacita':   grade == 'A++',

            'entry_zone': {
                'low':     entry_data['entry_low'],
                'high':    entry_data['entry_high'],
                'optimal': entry,
            },

            'stop_loss':  sl,
            'risk_pct':   entry_data['risk_pct'],

            'take_profits': {
                'tp1': {'price': tp1, 'rr': rr1, 'close': 50,
                        'note': 'TP1 = Riski sifirla (SL -> Entry)'},
                'tp2': {'price': tp2, 'rr': rr2, 'close': 30},
                'tp3': {'price': tp3, 'rr': rr3, 'close': 20},
            },

            'confluences': {
                'htf_bias':        f"{direction.upper()} ({htf_bias['zone']})",
                'bias_strength':   htf_bias['strength'],
                'trend_4h':        htf_bias.get('trend', 'unknown'),
                'msb':             True,
                'crt':             crt is not None,
                'choch':           choch_confirmed,
                'fvg':             fvg is not None,
                'ob':              ob is not None,
                'smt':             smt is not None,
                'session':         session,
                'session_quality': session_quality,
                'kill_zone':       kill_zone,
                'judas_swing':     judas_aligned,
                'spooling':        spooling,
                'spooling_name':   sp_name,
                'ce_proximity':    ce_proximity,
                'tgif':            is_friday,
            },

            'fib_levels': {
                'fib_50':  htf_bias.get('fib_50'),
                'fib_62':  htf_bias.get('fib_62'),
                'fib_705': htf_bias.get('fib_705'),
                'fib_79':  htf_bias.get('fib_79'),
            },

            'crt': {
                'found':          crt is not None,
                'type':           crt['type'] if crt else None,
                'swing_high':     round(htf_bias['swing_high'], 6),
                'swing_low':      round(htf_bias['swing_low'], 6),
                'choch_price':    round(msb['broken_level'], 6),
                'choch_confirmed': choch_confirmed,
            },

            'breakdown':    breakdown,
            'smt_detail':   {'type': smt['type'], 'description': smt['description']} if smt else None,

            'risk_management': {
                'tp1_action': 'TP1 gelince SL entry fiyatina cek (risksiz pozisyon)',
                'tp2_action': 'TP2 gelince yarim kapat',
                'tp3_action': 'TP3 tam hedef',
            },
        }


signal_generator = SignalGenerator()
