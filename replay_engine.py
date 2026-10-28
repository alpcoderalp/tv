import json
import csv
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/klines/PONSUSDT_last_1m.json', 'r', encoding='utf-8') as f:
    pons_klines = {int(k[0]): k for k in json.load(f)}

with open('scratch/klines/CHIPUSDT_last_1m.json', 'r', encoding='utf-8') as f:
    chip_klines = {int(k[0]): k for k in json.load(f)}

# Load complete cohort parents from parse_all_parents_complete
sys.path.append('scratch')
from parse_all_parents_complete import valid_cohort_parents

tick_sizes = {'CHIPUSDT': 0.00001, 'PONSUSDT': 0.0001}

def run_replay(mode='pessimistic'):
    results = {}
    for pid, p in valid_cohort_parents.items():
        sym = p['symbol']
        side = p['side']
        entry_px = p['entry_price']
        entry_qty = p['entry_qty']
        baseline_sl = p['baseline_sl']
        r1 = p['r1']
        r2 = p['r2']
        r3 = p['r3']
        tick = tick_sizes[sym]
        start_ts = int(p['dt'].timestamp() * 1000)
        
        # 4 hours window max
        end_ts = start_ts + 4 * 3600 * 1000
        kline_dict = pons_klines if 'PONS' in sym else chip_klines
        bars = [k for ts, k in sorted(kline_dict.items()) if start_ts <= ts <= end_ts]
        
        if not bars or entry_px <= 0 or baseline_sl <= 0:
            results[pid] = {'pnl': 0.0, 'tp1_hit': False, 'close_reason': 'NO_DATA'}
            continue
        
        rem_qty = entry_qty
        realized_pnl = 0.0
        tp1_hit = False
        current_sl = baseline_sl
        peak_px = entry_px
        closed = False
        close_reason = ''
        
        for bar in bars:
            b_high = float(bar[2])
            b_low = float(bar[3])
            b_close = float(bar[4])
            
            if side == 'LONG':
                # Check ambiguity: Does bar touch both current_sl and r1 (if not tp1_hit)?
                ambiguous_tp1 = (not tp1_hit and b_low <= current_sl and b_high >= r1)
                
                if ambiguous_tp1:
                    if mode == 'pessimistic':
                        # SL hit first!
                        realized_pnl += rem_qty * (current_sl - entry_px)
                        closed = True
                        close_reason = 'SL_HIT_BEFORE_TP1'
                        break
                    else:
                        # TP1 hit first!
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_pnl += tp_qty * (r1 - entry_px)
                        rem_qty -= tp_qty
                        tp1_hit = True
                        current_sl = max(current_sl, entry_px) # Move to BE
                        # Then in same bar, did it also hit BE?
                        if b_low <= current_sl:
                            realized_pnl += rem_qty * (current_sl - entry_px)
                            closed = True
                            close_reason = 'TP1_THEN_BE_SAME_BAR'
                            break
                        continue
                
                # Normal SL check
                if b_low <= current_sl:
                    realized_pnl += rem_qty * (current_sl - entry_px)
                    closed = True
                    close_reason = 'SL_TRIGGERED'
                    break
                
                if b_high > peak_px:
                    peak_px = b_high
                
                # TP1 check
                if not tp1_hit and b_high >= r1:
                    tp1_hit = True
                    tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                    realized_pnl += tp_qty * (r1 - entry_px)
                    rem_qty -= tp_qty
                    current_sl = max(current_sl, entry_px)
                
                # 2R trailing ratchet check (Quantized correctly!)
                if tp1_hit and b_high >= r2:
                    peak_pct = ((peak_px - entry_px) / entry_px) * 100
                    level = int(peak_pct // 0.2)
                    cand_sl = entry_px * (1 + (level * 0.001))
                    cand_sl_q = round(round(cand_sl / tick) * tick, 5 if sym == 'CHIPUSDT' else 4)
                    if peak_px >= r3:
                        cand_sl_q = max(cand_sl_q, r2)
                    current_sl = max(current_sl, cand_sl_q)
                    
            else: # SHORT
                ambiguous_tp1 = (not tp1_hit and b_high >= current_sl and b_low <= r1)
                if ambiguous_tp1:
                    if mode == 'pessimistic':
                        realized_pnl += rem_qty * (entry_px - current_sl)
                        closed = True
                        close_reason = 'SL_HIT_BEFORE_TP1'
                        break
                    else:
                        tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                        realized_pnl += tp_qty * (entry_px - r1)
                        rem_qty -= tp_qty
                        tp1_hit = True
                        current_sl = min(current_sl, entry_px)
                        if b_high >= current_sl:
                            realized_pnl += rem_qty * (entry_px - current_sl)
                            closed = True
                            close_reason = 'TP1_THEN_BE_SAME_BAR'
                            break
                        continue
                
                if b_high >= current_sl:
                    realized_pnl += rem_qty * (entry_px - current_sl)
                    closed = True
                    close_reason = 'SL_TRIGGERED'
                    break
                
                if b_low < peak_px:
                    peak_px = b_low
                
                if not tp1_hit and b_low <= r1:
                    tp1_hit = True
                    tp_qty = round(entry_qty * 0.5, 0 if sym == 'CHIPUSDT' else 1)
                    realized_pnl += tp_qty * (entry_px - r1)
                    rem_qty -= tp_qty
                    current_sl = min(current_sl, entry_px)
                
                if tp1_hit and b_low <= r2:
                    peak_pct = ((entry_px - peak_px) / entry_px) * 100
                    level = int(peak_pct // 0.2)
                    cand_sl = entry_px * (1 - (level * 0.001))
                    cand_sl_q = round(round(cand_sl / tick) * tick, 5 if sym == 'CHIPUSDT' else 4)
                    if peak_px >= r3:
                        cand_sl_q = min(cand_sl_q, r2)
                    current_sl = min(current_sl, cand_sl_q)
        
        if not closed:
            last_px = float(bars[-1][4])
            realized_pnl += rem_qty * (last_px - entry_px if side == 'LONG' else entry_px - last_px)
            close_reason = 'TIMEOUT_4H'
            
        results[pid] = {'pnl': realized_pnl, 'tp1_hit': tp1_hit, 'close_reason': close_reason}
    return results

pessimistic = run_replay('pessimistic')
optimistic = run_replay('optimistic')

tot_pess = sum(r['pnl'] for r in pessimistic.values())
tot_opt = sum(r['pnl'] for r in optimistic.values())

print(f"\nReplay PnL Pessimistic (SL first on ambiguity): {tot_pess:+8.4f} USDT")
print(f"Replay PnL Optimistic (TP1 first on ambiguity):  {tot_opt:+8.4f} USDT")
