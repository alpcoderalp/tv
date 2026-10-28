"""
Deterministic Replay Engine for Hummingbot TV Signal Strategy Audit
Replays exact strategy rules on 1-minute LastPrice and MarkPrice Bybit klines.
Fully self-contained: loads data from data/ directory.
Strictly respects cohort start (2026-10-23 09:31:39 UTC) and end (2026-10-28 13:00:00 UTC) cutoffs.
"""

import os
import json
import csv
import sys
import argparse
from datetime import datetime, timezone
from collections import defaultdict

START_CUTOFF_MS = 1792747899000  # 2026-10-23 09:31:39 UTC
END_CUTOFF_MS   = 1793192400000  # 2026-10-28 13:00:00 UTC

def parse_args():
    parser = argparse.ArgumentParser(description="Deterministic Strategy Replay Engine")
    parser.add_argument("--mode", choices=["pessimistic", "optimistic"], default="pessimistic",
                        help="Intra-candle tie-breaker mode for same-bar TP1/SL conflict")
    parser.add_argument("--slippage", choices=["standard", "stress_worst_candle"], default="standard",
                        help="Execution model: 'standard' fills at trigger SL, 'stress_worst_candle' fills at extreme candle wick")
    parser.add_argument("--with-4h-timeout", action="store_true", default=False,
                        help="Enable artificial 4-hour timeout (sensitivity test only)")
    parser.add_argument("--taker-fee", type=float, default=0.00055,
                        help="Exchange taker fee per side (default 0.055%)")
    parser.add_argument("--maker-fee", type=float, default=0.00020,
                        help="Exchange maker fee per side for TP1 limit orders (default 0.020%)")
    parser.add_argument("--output-csv", type=str, default=None,
                        help="Optional CSV output path for per-parent replay results")
    return parser.parse_args()

def run_replay(mode="pessimistic", slippage="standard", with_4h_timeout=False,
               taker_fee=0.00055, maker_fee=0.00020):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')

    # Load klines from data/klines
    kline_dir = os.path.join(data_dir, 'klines')
    with open(os.path.join(kline_dir, 'PONSUSDT_last_1m.json'), 'r', encoding='utf-8') as f:
        pons_last = {int(k[0]): k for k in json.load(f)}
    with open(os.path.join(kline_dir, 'PONSUSDT_mark_1m.json'), 'r', encoding='utf-8') as f:
        pons_mark = {int(k[0]): k for k in json.load(f)}
    with open(os.path.join(kline_dir, 'CHIPUSDT_last_1m.json'), 'r', encoding='utf-8') as f:
        chip_last = {int(k[0]): k for k in json.load(f)}
    with open(os.path.join(kline_dir, 'CHIPUSDT_mark_1m.json'), 'r', encoding='utf-8') as f:
        chip_mark = {int(k[0]): k for k in json.load(f)}

    # Load cohort parents from data/cohort_parents.json
    parents_file = os.path.join(data_dir, 'cohort_parents.json')
    with open(parents_file, 'r', encoding='utf-8') as f:
        cohort_parents = json.load(f)

    tick_sizes = {'CHIPUSDT': 0.00001, 'PONSUSDT': 0.0001}
    results = {}
    tp1_sl_ambiguities = 0
    be_trailing_ambiguities = 0

    for pid, p in cohort_parents.items():
        sym = p['symbol']
        side = p['side']
        entry_px = float(p['entry_price'])
        entry_qty = float(p['entry_qty'])
        baseline_sl = float(p['baseline_sl'])
        r1 = float(p['r1'])
        r2 = float(p['r2'])
        r3 = float(p['r3'])
        r_dist = abs(entry_px - baseline_sl)
        tick = tick_sizes[sym]
        start_ts = int(p['timestamp_ms'])

        last_dict = pons_last if 'PONS' in sym else chip_last
        mark_dict = pons_mark if 'PONS' in sym else chip_mark

        # STRICT END CUTOFF: only bars where start_ts <= ts <= END_CUTOFF_MS
        common_ts = sorted([ts for ts in last_dict if start_ts <= ts <= END_CUTOFF_MS and ts in mark_dict])
        if not common_ts or entry_px <= 0 or baseline_sl <= 0:
            results[pid] = {
                'parent_id': pid, 'symbol': sym, 'side': side, 'entry_price': entry_px, 'qty': entry_qty,
                'status': 'NO_DATA', 'close_reason': 'NO_DATA', 'tp1_hit': False, 'bars_held': 0,
                'realized_gross': 0.0, 'realized_fees': 0.0, 'realized_net': 0.0,
                'unrealized_gross': 0.0, 'unrealized_net': 0.0, 'total_net': 0.0,
                'ambiguity_tp1_sl': False, 'ambiguity_be_trailing': False, 'final_sl': baseline_sl
            }
            continue

        rem_qty = entry_qty
        realized_gross = 0.0
        realized_fees = entry_qty * entry_px * taker_fee  # Entry taker fee
        tp1_hit = False
        current_sl = baseline_sl
        peak_px = entry_px
        closed = False
        close_reason = ''
        close_ts = None
        bars_held = 0
        experienced_tp1_sl_ambiguity = False
        experienced_be_trailing_ambiguity = False

        for idx, ts in enumerate(common_ts):
            bars_held += 1
            l_bar = last_dict[ts]
            m_bar = mark_dict[ts]

            l_open, l_high, l_low, l_close = float(l_bar[1]), float(l_bar[2]), float(l_bar[3]), float(l_bar[4])
            m_open, m_high, m_low, m_close = float(m_bar[1]), float(m_bar[2]), float(m_bar[3]), float(m_bar[4])

            # Optional 4-hour exit check
            if with_4h_timeout and bars_held >= 240:
                exit_px = l_close
                realized_gross += rem_qty * ((exit_px - entry_px) if side == 'LONG' else (entry_px - exit_px))
                realized_fees += rem_qty * exit_px * taker_fee
                rem_qty = 0.0
                closed = True
                close_reason = 'TIMEOUT_4H'
                close_ts = ts
                break

            if side == 'LONG':
                # Triggered by MarkPrice!
                mark_hits_sl = (m_low <= current_sl)
                last_hits_tp1 = (l_high >= r1) if not tp1_hit else False

                if mark_hits_sl and last_hits_tp1 and not tp1_hit:
                    experienced_tp1_sl_ambiguity = True
                    tp1_sl_ambiguities += 1

                if mode == 'pessimistic':
                    # Pessimistic: check SL first
                    if mark_hits_sl:
                        exit_px = min(current_sl, l_low) if slippage == 'stress_worst_candle' else current_sl
                        realized_gross += rem_qty * (exit_px - entry_px)
                        realized_fees += rem_qty * exit_px * taker_fee
                        rem_qty = 0.0
                        closed = True
                        close_reason = 'SL_TRIGGERED'
                        close_ts = ts
                        break

                    if last_hits_tp1:
                        tp1_hit = True
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_gross += tp_qty * (r1 - entry_px)
                        realized_fees += tp_qty * r1 * maker_fee  # Limit maker fee
                        rem_qty -= tp_qty
                        new_sl = max(current_sl, entry_px)  # Move to BE
                        # Same-bar BE check
                        if m_low <= new_sl:
                            experienced_be_trailing_ambiguity = True
                            be_trailing_ambiguities += 1
                            exit_px = min(new_sl, l_low) if slippage == 'stress_worst_candle' else new_sl
                            realized_gross += rem_qty * (exit_px - entry_px)
                            realized_fees += rem_qty * exit_px * taker_fee
                            rem_qty = 0.0
                            closed = True
                            close_reason = 'TP1_THEN_BE_SAME_BAR'
                            close_ts = ts
                            break
                        current_sl = new_sl
                else:
                    # Optimistic: check TP1 first
                    if last_hits_tp1:
                        tp1_hit = True
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_gross += tp_qty * (r1 - entry_px)
                        realized_fees += tp_qty * r1 * maker_fee
                        rem_qty -= tp_qty
                        new_sl = max(current_sl, entry_px)
                        if m_low <= new_sl:
                            experienced_be_trailing_ambiguity = True
                            be_trailing_ambiguities += 1
                        current_sl = new_sl
                    elif mark_hits_sl:
                        exit_px = min(current_sl, l_low) if slippage == 'stress_worst_candle' else current_sl
                        realized_gross += rem_qty * (exit_px - entry_px)
                        realized_fees += rem_qty * exit_px * taker_fee
                        rem_qty = 0.0
                        closed = True
                        close_reason = 'SL_TRIGGERED'
                        close_ts = ts
                        break

                # Trailing updates on Last Price high
                if l_high > peak_px:
                    peak_px = l_high

                if tp1_hit and l_high >= r2:
                    peak_pct = ((peak_px - entry_px) / entry_px) * 100
                    level = int(peak_pct // 0.2)
                    cand_sl = entry_px * (1 + (level * 0.001))
                    cand_sl_q = round(round(cand_sl / tick) * tick, 5 if sym == 'CHIPUSDT' else 4)
                    if peak_px >= r3 and r_dist > 0:
                        k_peak = min(int((peak_px - entry_px) // r_dist), 11)
                        floor = entry_px + (k_peak - 1) * r_dist if k_peak >= 3 else 0
                        cand_sl_q = max(cand_sl_q, floor, r2)
                    current_sl = max(current_sl, cand_sl_q)

            else:  # SHORT
                mark_hits_sl = (m_high >= current_sl)
                last_hits_tp1 = (l_low <= r1) if not tp1_hit else False

                if mark_hits_sl and last_hits_tp1 and not tp1_hit:
                    experienced_tp1_sl_ambiguity = True
                    tp1_sl_ambiguities += 1

                if mode == 'pessimistic':
                    if mark_hits_sl:
                        exit_px = max(current_sl, l_high) if slippage == 'stress_worst_candle' else current_sl
                        realized_gross += rem_qty * (entry_px - exit_px)
                        realized_fees += rem_qty * exit_px * taker_fee
                        rem_qty = 0.0
                        closed = True
                        close_reason = 'SL_TRIGGERED'
                        close_ts = ts
                        break

                    if last_hits_tp1:
                        tp1_hit = True
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_gross += tp_qty * (entry_px - r1)
                        realized_fees += tp_qty * r1 * maker_fee
                        rem_qty -= tp_qty
                        new_sl = min(current_sl, entry_px)
                        if m_high >= new_sl:
                            experienced_be_trailing_ambiguity = True
                            be_trailing_ambiguities += 1
                            exit_px = max(new_sl, l_high) if slippage == 'stress_worst_candle' else new_sl
                            realized_gross += rem_qty * (entry_px - exit_px)
                            realized_fees += rem_qty * exit_px * taker_fee
                            rem_qty = 0.0
                            closed = True
                            close_reason = 'TP1_THEN_BE_SAME_BAR'
                            close_ts = ts
                            break
                        current_sl = new_sl
                else:
                    if last_hits_tp1:
                        tp1_hit = True
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_gross += tp_qty * (entry_px - r1)
                        realized_fees += tp_qty * r1 * maker_fee
                        rem_qty -= tp_qty
                        new_sl = min(current_sl, entry_px)
                        if m_high >= new_sl:
                            experienced_be_trailing_ambiguity = True
                            be_trailing_ambiguities += 1
                        current_sl = new_sl
                    elif mark_hits_sl:
                        exit_px = max(current_sl, l_high) if slippage == 'stress_worst_candle' else current_sl
                        realized_gross += rem_qty * (entry_px - exit_px)
                        realized_fees += rem_qty * exit_px * taker_fee
                        rem_qty = 0.0
                        closed = True
                        close_reason = 'SL_TRIGGERED'
                        close_ts = ts
                        break

                if l_low < peak_px:
                    peak_px = l_low

                # FIXED SHORT 3R AND RATCHET FLOOR LOGIC
                if tp1_hit and l_low <= r2:
                    peak_pct = ((entry_px - peak_px) / entry_px) * 100
                    level = int(peak_pct // 0.2)
                    cand_sl = entry_px * (1 - (level * 0.001))
                    cand_sl_q = round(round(cand_sl / tick) * tick, 5 if sym == 'CHIPUSDT' else 4)
                    if peak_px <= r3 and r_dist > 0:
                        k_peak = min(int((entry_px - peak_px) // r_dist), 11)
                        floor = entry_px - (k_peak - 1) * r_dist if k_peak >= 3 else 0
                        cands = [c for c in (floor, cand_sl_q, r2) if c > 0]
                        cand_sl_q = min(cands)
                    current_sl = min(current_sl, cand_sl_q)

        # Realized vs Unrealized separation
        realized_net = realized_gross - realized_fees
        unrealized_gross = 0.0
        unrealized_net = 0.0

        if not closed and rem_qty > 0:
            final_bar = last_dict[common_ts[-1]]
            final_px = float(final_bar[4])  # 13:00:00 UTC cutoff price
            unrealized_gross = rem_qty * ((final_px - entry_px) if side == 'LONG' else (entry_px - final_px))
            unrealized_net = unrealized_gross - (rem_qty * final_px * taker_fee)
            close_reason = 'OPEN_AT_END'

        results[pid] = {
            'parent_id': pid,
            'symbol': sym,
            'side': side,
            'entry_price': entry_px,
            'qty': entry_qty,
            'rem_qty': rem_qty,
            'status': 'CLOSED' if closed else 'OPEN_AT_END',
            'close_reason': close_reason,
            'tp1_hit': tp1_hit,
            'realized_gross': realized_gross,
            'realized_fees': realized_fees,
            'realized_net': realized_net,
            'unrealized_gross': unrealized_gross,
            'unrealized_net': unrealized_net,
            'total_net': realized_net + unrealized_net,
            'bars_held': bars_held,
            'ambiguity_tp1_sl': experienced_tp1_sl_ambiguity,
            'ambiguity_be_trailing': experienced_be_trailing_ambiguity,
            'final_sl': current_sl
        }

    return results, tp1_sl_ambiguities, be_trailing_ambiguities

if __name__ == "__main__":
    args = parse_args()
    results, tp_sl_amb, be_amb = run_replay(
        mode=args.mode,
        slippage=args.slippage,
        with_4h_timeout=args.with_4h_timeout,
        taker_fee=args.taker_fee,
        maker_fee=args.maker_fee
    )
    tot_realized_gross = sum(r['realized_gross'] for r in results.values())
    tot_realized_fees  = sum(r['realized_fees'] for r in results.values())
    tot_realized_net   = sum(r['realized_net'] for r in results.values())
    tot_unrealized_net = sum(r['unrealized_net'] for r in results.values())
    tot_net            = sum(r['total_net'] for r in results.values())
    tp1_count          = sum(1 for r in results.values() if r['tp1_hit'])
    open_count         = sum(1 for r in results.values() if r['status'] == 'OPEN_AT_END')

    print(f"--- REPLAY RUN [{args.mode.upper()} | Slippage: {args.slippage.upper()} | 4h Timeout: {args.with_4h_timeout}] ---")
    print(f"Total Parents Replayed:      {len(results)}")
    print(f"TP1 Achieved:                {tp1_count} / {len(results)}")
    print(f"Positions Closed:            {len(results) - open_count} / {len(results)}")
    print(f"Positions Open at Cutoff:    {open_count} / {len(results)}")
    print(f"Realized Gross PnL:          {tot_realized_gross:+9.4f} USDT")
    print(f"Realized Fees Paid:          {tot_realized_fees:9.4f} USDT")
    print(f"Realized Net PnL:            {tot_realized_net:+9.4f} USDT")
    print(f"Unrealized Net PnL (Open):   {tot_unrealized_net:+9.4f} USDT")
    print(f"Total Net PnL (Combined):    {tot_net:+9.4f} USDT")
    print(f"Intra-bar TP1/SL Ambiguity:  {tp_sl_amb} trades")
    print(f"Intra-bar BE Ambiguity:      {be_amb} trades")

    if args.output_csv:
        with open(args.output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(next(iter(results.values())).keys()))
            writer.writeheader()
            writer.writerows(results.values())
        print(f"Wrote per-parent replay to {args.output_csv}")
