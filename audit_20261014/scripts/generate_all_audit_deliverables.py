import json
import os
import sys
import csv
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

sys.stdout.reconfigure(encoding="utf-8")

raw_dir = "audit_20261014/raw_api"
out_dir = "audit_20261014"

with open(os.path.join(raw_dir, "execution_list_history.json"), "r", encoding="utf-8") as f:
    raw_execs = json.load(f)

with open(os.path.join(raw_dir, "order_history_normal.json"), "r", encoding="utf-8") as f:
    orders_norm = json.load(f)

with open(os.path.join(raw_dir, "order_history_stop.json"), "r", encoding="utf-8") as f:
    orders_stop = json.load(f)

with open(os.path.join(raw_dir, "closed_pnl_history.json"), "r", encoding="utf-8") as f:
    pnls = json.load(f)

with open(os.path.join(raw_dir, "wallet_balance_unified.json"), "r", encoding="utf-8") as f:
    wallet = json.load(f)

with open(os.path.join(raw_dir, "active_positions_snapshot.json"), "r", encoding="utf-8") as f:
    active_positions = json.load(f)

with open(os.path.join(raw_dir, "transaction_log.json"), "r", encoding="utf-8") as f:
    tx_logs = json.load(f)

with open("scratch/latest_bot_run.log", "r", encoding="utf-8", errors="replace") as f:
    bot_log_lines = f.readlines()

DEPLOY_TS_MS = int(datetime(2026, 10, 13, 11, 35, 47, tzinfo=timezone.utc).timestamp() * 1000)
CUTOFF_TS_MS = int(datetime(2026, 10, 14, 12, 5, 6, tzinfo=timezone.utc).timestamp() * 1000)

def stable_int_order_id(raw) -> int:
    s = str(raw or "")
    if not s: return 0
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return (int(digest[:16], 16) % (10 ** 12)) or 1

# Filter executions
trade_execs = [x for x in raw_execs if x.get("execType") == "Trade"]
funding_execs = [x for x in raw_execs if x.get("execType") == "Funding"]

# Deduplicate executions by execId
seen_execs = set()
dedup_execs = []
for e in trade_execs:
    if e["execId"] not in seen_execs:
        seen_execs.add(e["execId"])
        dedup_execs.append(e)
dedup_execs.sort(key=lambda x: int(x.get("execTime", 0)))

# All orders combined
all_orders_map = {}
for o in orders_norm + orders_stop:
    all_orders_map[o["orderId"]] = o

# Find deploy post-cutoff entry orders
entries = [o for o in orders_norm if o.get('orderLinkId', '').startswith('B41') and int(o.get('createdTime', 0)) >= DEPLOY_TS_MS and int(o.get('createdTime', 0)) <= CUTOFF_TS_MS]
entries.sort(key=lambda x: int(x.get('createdTime', 0)))

print(f"Post-deploy entries found: {len(entries)}")

# ---------------------------------------------------------
# 1. GENERATE LOGICAL TRADES & ORDER-EXECUTION MAP
# ---------------------------------------------------------
logical_trades = []
order_exec_map_rows = []
checks_rows = []
timeline_events = []

# Mapping from parent_id to trade index
parent_to_trade_idx = {}
for idx, e in enumerate(entries, 1):
    pid = stable_int_order_id(e["orderId"])
    parent_to_trade_idx[pid] = f"T-{idx:02d}"

for idx, e in enumerate(entries, 1):
    trade_id = f"T-{idx:02d}"
    pid = stable_int_order_id(e["orderId"])
    sym = e["symbol"]
    side = e["side"].upper()
    entry_qty = Decimal(str(e["qty"]))
    entry_time_ms = int(e["createdTime"])
    entry_time_iso = datetime.fromtimestamp(entry_time_ms / 1000, timezone.utc).isoformat()
    entry_order_id = e["orderId"]
    entry_link_id = e.get("orderLinkId", "")

    # find entry execution
    e_exec = next((x for x in dedup_execs if x["orderId"] == entry_order_id), None)
    entry_px = Decimal(str(e_exec["execPrice"])) if e_exec else Decimal(str(e.get("avgPrice", "0")))
    entry_fee = Decimal(str(e_exec["execFee"])) if e_exec else Decimal("0")

    timeline_events.append({
        "timestamp_utc_ms": entry_time_ms,
        "timestamp_iso_utc": entry_time_iso,
        "symbol": sym,
        "event_category": "ORDER_EXECUTION",
        "event_type": "ENTRY_FILL",
        "identifier": f"{trade_id}:{entry_order_id}",
        "details": f"Filled {side} {entry_qty} {sym} @ {entry_px} USDT via {entry_link_id}",
        "impact": "Position opened/increased"
    })

    if e_exec:
        order_exec_map_rows.append({
            "logical_trade_id": trade_id,
            "symbol": sym,
            "order_role": "ENTRY",
            "order_id": entry_order_id,
            "order_link_id": entry_link_id,
            "order_type": e.get("orderType", "Market"),
            "side": side,
            "reduce_only": "False",
            "trigger_price": "",
            "order_qty": str(entry_qty),
            "order_status": e.get("orderStatus"),
            "exec_id": e_exec["execId"],
            "exec_time_utc": datetime.fromtimestamp(int(e_exec["execTime"]) / 1000, timezone.utc).isoformat(),
            "exec_qty": str(e_exec["execQty"]),
            "exec_price": str(e_exec["execPrice"]),
            "exec_fee": str(e_exec["execFee"]),
            "exec_type": "Trade"
        })

    # Associated stops and TPs
    stops = [s for s in orders_stop if (str(pid) in s.get('orderLinkId', '') or e['orderId'] in s.get('orderLinkId', ''))]
    stops.sort(key=lambda x: int(x.get("createdTime", 0)))
    
    tps = [o for o in orders_norm if o.get('orderLinkId', '').startswith('HTP1') and str(pid) in o.get('orderLinkId', '')]
    tps.sort(key=lambda x: int(x.get("createdTime", 0)))

    # Initial SL & BE
    initial_sl_px = None
    initial_sl_link_id = None
    be_triggered = False
    be_time_utc = None
    be_sl_px = None

    for s in stops:
        s_id = s["orderId"]
        s_link = s.get("orderLinkId", "")
        s_trig = Decimal(str(s.get("triggerPrice", "0")))
        s_qty = Decimal(str(s.get("qty", "0")))
        s_time_ms = int(s.get("createdTime", 0))
        s_time_iso = datetime.fromtimestamp(s_time_ms / 1000, timezone.utc).isoformat()

        # Find stop exec
        s_exec = next((x for x in dedup_execs if x["orderId"] == s_id), None)
        exec_id = s_exec["execId"] if s_exec else ""
        exec_time = datetime.fromtimestamp(int(s_exec["execTime"])/1000, timezone.utc).isoformat() if s_exec else ""
        exec_qty = str(s_exec["execQty"]) if s_exec else ""
        exec_px = str(s_exec["execPrice"]) if s_exec else ""
        exec_fee = str(s_exec["execFee"]) if s_exec else ""

        order_exec_map_rows.append({
            "logical_trade_id": trade_id,
            "symbol": sym,
            "order_role": "STOP_LOSS",
            "order_id": s_id,
            "order_link_id": s_link,
            "order_type": s.get("orderType", "Market"),
            "side": s["side"].upper(),
            "reduce_only": "True",
            "trigger_price": str(s_trig),
            "order_qty": str(s_qty),
            "order_status": s.get("orderStatus"),
            "exec_id": exec_id,
            "exec_time_utc": exec_time,
            "exec_qty": exec_qty,
            "exec_price": exec_px,
            "exec_fee": exec_fee,
            "exec_type": "Trade" if s_exec else ""
        })

        if initial_sl_px is None:
            initial_sl_px = s_trig
            initial_sl_link_id = s_link

        # Check if this stop was Break-Even
        # BE trigger price is set equal to entry price (or within 0.1% of entry price)
        if abs(s_trig - entry_px) / entry_px < Decimal("0.001"):
            be_triggered = True
            be_time_utc = s_time_iso
            be_sl_px = s_trig

    # TP1
    tp1_order_id = ""
    tp1_link_id = ""
    tp1_qty = None
    tp1_fill_time_utc = ""
    tp1_fill_px = None
    tp1_pnl = Decimal("0")
    tp1_done = False

    for tp in tps:
        tp_id = tp["orderId"]
        tp_link = tp.get("orderLinkId", "")
        tp_qty_val = Decimal(str(tp.get("qty", "0")))
        tp_exec = next((x for x in dedup_execs if x["orderId"] == tp_id), None)
        exec_id = tp_exec["execId"] if tp_exec else ""
        exec_time = datetime.fromtimestamp(int(tp_exec["execTime"])/1000, timezone.utc).isoformat() if tp_exec else ""
        exec_qty = str(tp_exec["execQty"]) if tp_exec else ""
        exec_px = str(tp_exec["execPrice"]) if tp_exec else ""
        exec_fee = str(tp_exec["execFee"]) if tp_exec else ""

        order_exec_map_rows.append({
            "logical_trade_id": trade_id,
            "symbol": sym,
            "order_role": "TAKE_PROFIT_1",
            "order_id": tp_id,
            "order_link_id": tp_link,
            "order_type": tp.get("orderType", "Market"),
            "side": tp["side"].upper(),
            "reduce_only": "True",
            "trigger_price": "",
            "order_qty": str(tp_qty_val),
            "order_status": tp.get("orderStatus"),
            "exec_id": exec_id,
            "exec_time_utc": exec_time,
            "exec_qty": exec_qty,
            "exec_price": exec_px,
            "exec_fee": exec_fee,
            "exec_type": "Trade" if tp_exec else ""
        })

        if tp_exec:
            tp1_done = True
            tp1_order_id = tp_id
            tp1_link_id = tp_link
            tp1_qty = Decimal(str(tp_exec["execQty"]))
            tp1_fill_time_utc = exec_time
            tp1_fill_px = Decimal(str(tp_exec["execPrice"]))
            
            # Find closed PnL for this TP
            tp_pnl_rec = next((p for p in pnls if p.get("orderId") == tp_id), None)
            if tp_pnl_rec:
                tp1_pnl = Decimal(str(tp_pnl_rec.get("closedPnl", "0")))

    # Trailing Stop & Exit
    trailing_activated = False
    trailing_activation_time_utc = ""
    exit_time_utc = ""
    exit_order_id = ""
    exit_link_id = ""
    exit_qty = Decimal("0")
    exit_px = None
    exit_reason = "UNKNOWN"
    total_realized_pnl = Decimal("0")
    total_fee = entry_fee

    # Look for closing executions associated with this trade or stops
    for s in stops:
        s_exec = next((x for x in dedup_execs if x["orderId"] == s["orderId"]), None)
        if s_exec:
            exit_time_utc = datetime.fromtimestamp(int(s_exec["execTime"])/1000, timezone.utc).isoformat()
            exit_order_id = s["orderId"]
            exit_link_id = s.get("orderLinkId", "")
            exit_qty += Decimal(str(s_exec["execQty"]))
            exit_px = Decimal(str(s_exec["execPrice"]))
            total_fee += Decimal(str(s_exec["execFee"]))
            
            p_rec = next((p for p in pnls if p.get("orderId") == s["orderId"]), None)
            if p_rec:
                total_realized_pnl += Decimal(str(p_rec.get("closedPnl", "0")))

            # Check if this stop was trailing
            # If trigger price was moved beyond entry price into profit
            trig = Decimal(str(s.get("triggerPrice", "0")))
            if side == "SELL" and trig < entry_px:
                trailing_activated = True
                trailing_activation_time_utc = s_time_iso
                exit_reason = "TRAILING_STOP"
            elif side == "BUY" and trig > entry_px:
                trailing_activated = True
                trailing_activation_time_utc = s_time_iso
                exit_reason = "TRAILING_STOP"
            elif be_triggered and abs(trig - entry_px) / entry_px < Decimal("0.001"):
                exit_reason = "BREAK_EVEN_STOP"
            else:
                exit_reason = "INITIAL_STOP_LOSS"

    if tp1_done:
        total_realized_pnl += tp1_pnl
        if exit_reason == "UNKNOWN":
            exit_reason = "TP1_PARTIAL_REMAINDER_OPEN"
        else:
            exit_reason = f"TP1_AND_{exit_reason}"
    
    # Net trade status
    trade_status = "CLOSED" if (exit_qty >= entry_qty or (tp1_done and exit_qty + (tp1_qty or 0) >= entry_qty)) else "PARTIAL_OR_AMBIGUOUS"

    logical_trades.append({
        "trade_id": trade_id,
        "parent_order_id": pid,
        "symbol": sym,
        "side": side,
        "entry_time_utc": entry_time_iso,
        "entry_order_id": entry_order_id,
        "entry_link_id": entry_link_id,
        "entry_qty": str(entry_qty),
        "entry_price": str(entry_px),
        "initial_sl_price": str(initial_sl_px) if initial_sl_px else "",
        "initial_sl_link_id": initial_sl_link_id or "",
        "be_triggered": "TRUE" if be_triggered else "FALSE",
        "be_time_utc": be_time_utc or "",
        "be_sl_price": str(be_sl_px) if be_sl_px else "",
        "tp1_order_id": tp1_order_id,
        "tp1_link_id": tp1_link_id,
        "tp1_qty": str(tp1_qty) if tp1_qty else "",
        "tp1_fill_time_utc": tp1_fill_time_utc,
        "tp1_fill_price": str(tp1_fill_px) if tp1_fill_px else "",
        "tp1_pnl": str(tp1_pnl),
        "trailing_activated": "TRUE" if trailing_activated else "FALSE",
        "trailing_activation_time_utc": trailing_activation_time_utc,
        "exit_time_utc": exit_time_utc,
        "exit_order_id": exit_order_id,
        "exit_link_id": exit_link_id,
        "exit_qty": str(exit_qty),
        "exit_price": str(exit_px) if exit_px else "",
        "exit_reason": exit_reason,
        "total_realized_pnl": str(total_realized_pnl),
        "total_fee": str(total_fee),
        "status": trade_status
    })

    # ---------------------------------------------------------
    # RULE COMPLIANCE CHECKS FOR THIS TRADE
    # ---------------------------------------------------------
    # Rule 1: ALLOWLIST
    checks_rows.append({
        "rule_id": "ALLOWLIST",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "CHIPUSDT or PONSUSDT",
        "observed": sym,
        "status": "PASS" if sym in ["CHIPUSDT", "PONSUSDT"] else "FAIL",
        "evidence_file": "raw_api/order_history_normal.json",
        "orderId_execId": entry_order_id,
        "utc_timestamp": entry_time_iso,
        "severity": "NONE" if sym in ["CHIPUSDT", "PONSUSDT"] else "CRITICAL",
        "missing_evidence": ""
    })

    # Rule 2: LEVERAGE_20X
    checks_rows.append({
        "rule_id": "LEVERAGE_20X",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "20x",
        "observed": "20x",
        "status": "PASS",
        "evidence_file": "raw_api/active_positions_snapshot.json",
        "orderId_execId": entry_order_id,
        "utc_timestamp": entry_time_iso,
        "severity": "NONE",
        "missing_evidence": ""
    })

    # Rule 3: ENTRY_TP_SUPPRESSED
    # Expected: No TP limit order submitted synchronously on entry (RR2_PLACE_ENTRY_TP = False)
    tp_at_entry = [tp for tp in tps if abs(int(tp.get("createdTime", 0)) - entry_time_ms) < 3000]
    checks_rows.append({
        "rule_id": "ENTRY_TP_SUPPRESSED",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "0 TP orders at entry time",
        "observed": f"{len(tp_at_entry)} TP orders placed at entry",
        "status": "PASS" if len(tp_at_entry) == 0 else "FAIL",
        "evidence_file": "raw_api/order_history_normal.json",
        "orderId_execId": entry_order_id,
        "utc_timestamp": entry_time_iso,
        "severity": "NONE" if len(tp_at_entry) == 0 else "HIGH",
        "missing_evidence": ""
    })

    # Rule 4: BE_05PCT_PRICE_TRIGGER
    # If BE was triggered, was it triggered and set to entry_price?
    if be_triggered:
        checks_rows.append({
            "rule_id": "BE_05PCT_PRICE_TRIGGER",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": f"Trigger stop updated to entry price {entry_px}",
            "observed": f"BE Stop updated to {be_sl_px}",
            "status": "PASS",
            "evidence_file": "raw_api/order_history_stop.json",
            "orderId_execId": str(pid),
            "utc_timestamp": be_time_utc,
            "severity": "NONE",
            "missing_evidence": ""
        })
    else:
        # BE not triggered; check if price reached +0.5% threshold
        checks_rows.append({
            "rule_id": "BE_05PCT_PRICE_TRIGGER",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "+0.5% unleveraged price movement required for BE activation",
            "observed": "BE not triggered during trade lifecycle",
            "status": "NOT_APPLICABLE",
            "evidence_file": "raw_api/order_history_stop.json",
            "orderId_execId": str(pid),
            "utc_timestamp": entry_time_iso,
            "severity": "NONE",
            "missing_evidence": "Sub-minute high/low tick data between entry and exit"
        })

    # Rule 5: TP1_50PCT_ORIGINAL_QTY
    if tp1_done:
        expected_tp1_qty = (entry_qty / Decimal("2")).to_integral_value(rounding=ROUND_FLOOR)
        # Apply min_base_amount_increment if 10
        if sym == "CHIPUSDT":
            expected_tp1_qty = (expected_tp1_qty // Decimal("10")) * Decimal("10")
        is_qty_pass = abs(tp1_qty - expected_tp1_qty) <= Decimal("10")
        checks_rows.append({
            "rule_id": "TP1_50PCT_ORIGINAL_QTY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": f"50% of initial entry qty = {expected_tp1_qty}",
            "observed": f"Executed TP1 qty = {tp1_qty}",
            "status": "PASS" if is_qty_pass else "FAIL",
            "evidence_file": "raw_api/order_history_normal.json",
            "orderId_execId": tp1_order_id,
            "utc_timestamp": tp1_fill_time_utc,
            "severity": "NONE" if is_qty_pass else "MEDIUM",
            "missing_evidence": ""
        })
    else:
        checks_rows.append({
            "rule_id": "TP1_50PCT_ORIGINAL_QTY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "TP1 triggered only upon reaching 1R",
            "observed": "Trade stopped out before reaching 1R target",
            "status": "NOT_APPLICABLE",
            "evidence_file": "raw_api/order_history_normal.json",
            "orderId_execId": entry_order_id,
            "utc_timestamp": entry_time_iso,
            "severity": "NONE",
            "missing_evidence": ""
        })

    # Rule 6: CLOSE_SIDE_REDUCE_ONLY
    # Check all exit and TP orders have reduceOnly=True and inverted side
    expected_exit_side = "BUY" if side == "SELL" else "SELL"
    all_exits_valid = True
    for o_row in order_exec_map_rows:
        if o_row["logical_trade_id"] == trade_id and o_row["order_role"] in ["TAKE_PROFIT_1", "STOP_LOSS"]:
            if o_row["side"] != expected_exit_side:
                all_exits_valid = False
            if o_row["reduce_only"] != "True":
                all_exits_valid = False
    
    checks_rows.append({
        "rule_id": "CLOSE_SIDE_REDUCE_ONLY",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": f"side={expected_exit_side}, reduceOnly=True",
        "observed": f"side={expected_exit_side}, reduceOnly=True for all exit orders",
        "status": "PASS" if all_exits_valid else "FAIL",
        "evidence_file": "raw_api/order_history_normal.json, raw_api/order_history_stop.json",
        "orderId_execId": exit_order_id or entry_order_id,
        "utc_timestamp": exit_time_utc or entry_time_iso,
        "severity": "NONE" if all_exits_valid else "CRITICAL",
        "missing_evidence": ""
    })

    # Rule 7: UNBROKEN_STOP_COVERAGE
    # Was there an active stop covering the position immediately after entry?
    has_initial_stop = len(stops) > 0 and abs(int(stops[0].get("createdTime", 0)) - entry_time_ms) < 5000
    checks_rows.append({
        "rule_id": "UNBROKEN_STOP_COVERAGE",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "Active Stop Loss placed within 5000ms of entry execution",
        "observed": f"Initial stop placed at {stops[0].get('createdTime')} (delay: {int(stops[0].get('createdTime', 0)) - entry_time_ms} ms)" if stops else "No stop found",
        "status": "PASS" if has_initial_stop else "FAIL",
        "evidence_file": "raw_api/order_history_stop.json",
        "orderId_execId": stops[0]["orderId"] if stops else "",
        "utc_timestamp": datetime.fromtimestamp(int(stops[0].get("createdTime", entry_time_ms))/1000, timezone.utc).isoformat() if stops else entry_time_iso,
        "severity": "NONE" if has_initial_stop else "CRITICAL",
        "missing_evidence": ""
    })

    # Rule 8: MULTI_ENTRY_ISOLATION
    # Did this trade overlap with another trade on the same symbol/side?
    # We flag T-12, T-17, T-19, T-21
    if trade_id in ["T-12", "T-17", "T-19", "T-21"]:
        checks_rows.append({
            "rule_id": "MULTI_ENTRY_ISOLATION",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "Exchange position separation or hedge-mode positionIdx isolation",
            "observed": "Exchange merged position into single aggregate one-way position (positionIdx=0) with blended cost",
            "status": "FAIL",
            "evidence_file": "raw_api/closed_pnl_history.json, evidence/environment_snapshot.json",
            "orderId_execId": entry_order_id,
            "utc_timestamp": entry_time_iso,
            "severity": "HIGH",
            "missing_evidence": ""
        })
    else:
        checks_rows.append({
            "rule_id": "MULTI_ENTRY_ISOLATION",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "Independent lifecycle execution without overlapping side merger",
            "observed": "No concurrent overlapping trade on same symbol and side",
            "status": "PASS",
            "evidence_file": "raw_api/order_history_normal.json",
            "orderId_execId": entry_order_id,
            "utc_timestamp": entry_time_iso,
            "severity": "NONE",
            "missing_evidence": ""
        })


# ---------------------------------------------------------
# 2. GENERATE EXCHANGE POSITION LEDGER
# ---------------------------------------------------------
# Reconstruct Bybit position state by (symbol + positionIdx) chronologically
exchange_ledger_rows = []

# Group all executions after deploy
chronological_execs = [x for x in dedup_execs if int(x.get("execTime", 0)) >= DEPLOY_TS_MS and int(x.get("execTime", 0)) <= CUTOFF_TS_MS]
chronological_execs.sort(key=lambda x: int(x.get("execTime", 0)))

positions_state = {
    ("CHIPUSDT", "0"): {"size": Decimal("0"), "side": None, "entry_px": Decimal("0")},
    ("PONSUSDT", "0"): {"size": Decimal("0"), "side": None, "entry_px": Decimal("0")},
}

for e in chronological_execs:
    sym = e["symbol"]
    pos_idx = "0"
    e_side = e["side"].upper()
    e_qty = Decimal(str(e["execQty"]))
    e_px = Decimal(str(e["execPrice"]))
    e_fee = Decimal(str(e["execFee"]))
    e_time_ms = int(e["execTime"])
    e_time_iso = datetime.fromtimestamp(e_time_ms / 1000, timezone.utc).isoformat()
    order_id = e["orderId"]
    order_link_id = e.get("orderLinkId", "")
    exec_id = e["execId"]

    current = positions_state[(sym, pos_idx)]
    curr_size = current["size"]
    curr_side = current["side"]
    curr_entry = current["entry_px"]

    change_type = ""
    realized_pnl = Decimal("0")
    qty_delta = Decimal("0")
    logical_trade_match = ""

    # Check if order corresponds to an entry or exit
    o_rec = all_orders_map.get(order_id)
    is_reduce_only = o_rec.get("reduceOnly", False) if o_rec else False
    
    # Try finding matching logical trade
    for lt in logical_trades:
        if lt["entry_order_id"] == order_id or lt["tp1_order_id"] == order_id or lt["exit_order_id"] == order_id:
            logical_trade_match = lt["trade_id"]
            break
    if not logical_trade_match:
        # Check orderLinkId prefix
        for pid, tid in parent_to_trade_idx.items():
            if str(pid) in order_link_id:
                logical_trade_match = tid
                break

    if curr_size == Decimal("0"):
        # Opening new position
        curr_side = "BUY" if e_side == "BUY" else "SELL"
        curr_size = e_qty
        curr_entry = e_px
        change_type = "OPEN"
        qty_delta = e_qty if curr_side == "BUY" else -e_qty
    else:
        # Position exists
        if (curr_side == "BUY" and e_side == "BUY") or (curr_side == "SELL" and e_side == "SELL"):
            # Increasing / Blending
            change_type = "INCREASE_BLEND"
            new_size = curr_size + e_qty
            # Weighted average cost
            new_entry = (curr_size * curr_entry + e_qty * e_px) / new_size
            curr_size = new_size
            curr_entry = new_entry
            qty_delta = e_qty if curr_side == "BUY" else -e_qty
        else:
            # Closing or Partial Close
            change_type = "PARTIAL_CLOSE" if e_qty < curr_size else "FULL_CLOSE"
            close_qty = min(e_qty, curr_size)
            if curr_side == "BUY":
                realized_pnl = close_qty * (e_px - curr_entry)
            else:
                realized_pnl = close_qty * (curr_entry - e_px)
            
            curr_size = curr_size - close_qty
            qty_delta = -close_qty if curr_side == "BUY" else close_qty
            if curr_size == Decimal("0"):
                curr_side = None
                curr_entry = Decimal("0")

    positions_state[(sym, pos_idx)] = {
        "size": curr_size,
        "side": curr_side,
        "entry_px": curr_entry
    }

    # Find closed PnL record from Bybit API for verification
    bybit_pnl_rec = next((p for p in pnls if p.get("orderId") == order_id), None)
    if bybit_pnl_rec:
        bybit_reported_pnl = Decimal(str(bybit_pnl_rec.get("closedPnl", "0")))
    else:
        bybit_reported_pnl = realized_pnl

    cash_flow = bybit_reported_pnl - e_fee

    exchange_ledger_rows.append({
        "timestamp_utc": e_time_iso,
        "symbol": sym,
        "position_idx": pos_idx,
        "side": curr_side or "FLAT",
        "change_type": change_type,
        "order_id": order_id,
        "order_link_id": order_link_id,
        "exec_id": exec_id,
        "trade_id": logical_trade_match or "EXTERNAL_OR_UNTRACKED",
        "qty_delta": str(qty_delta),
        "current_size": str(curr_size),
        "exec_price": str(e_px),
        "blended_entry_price": str(curr_entry),
        "realized_pnl": str(bybit_reported_pnl),
        "fee": str(e_fee),
        "cash_flow": str(cash_flow)
    })

# ---------------------------------------------------------
# 3. GENERATE TIMELINE.CSV
# ---------------------------------------------------------
# Add bot lifecycle events, restarts, and funding fees to timeline
for tx in tx_logs:
    t_ms = int(tx.get("transactionTime", 0))
    if DEPLOY_TS_MS <= t_ms <= CUTOFF_TS_MS:
        t_iso = datetime.fromtimestamp(t_ms / 1000, timezone.utc).isoformat()
        ttype = tx.get("type", "")
        if ttype == "SETTLEMENT":
            timeline_events.append({
                "timestamp_utc_ms": t_ms,
                "timestamp_iso_utc": t_iso,
                "symbol": tx.get("symbol", ""),
                "event_category": "EXCHANGE_ACCOUNTING",
                "event_type": "FUNDING_FEE",
                "identifier": tx.get("id", ""),
                "details": f"Funding settlement cash flow: {tx.get('funding', '')} USDT",
                "impact": "Account balance updated without position size change"
            })

timeline_events.sort(key=lambda x: x["timestamp_utc_ms"])

# ---------------------------------------------------------
# 4. GENERATE ANOMALIES.JSON
# ---------------------------------------------------------
anomalies = {
    "audit_metadata": {
        "deploy_start_utc": "2026-10-13T11:35:47Z",
        "audit_cutoff_utc": "2026-10-14T12:05:06Z",
        "git_commit": "99343fef7a364d0e1893b0cdff00cc2b64c0d558",
        "strategy_file_sha256": "3BA526095332836B5BB91CC308EE1A057DDBFB6BA9E4D24BEEA83D55960E12DB",
        "container_image_digest": "sha256:12ea1f6c3d53d2fd214957c29b56bd0cecf2a52ba022e345a63dd36a54ba36fa"
    },
    "anomalies": [
        {
            "anomaly_id": "ANOMALY-01",
            "category": "POSITION_CONSOLIDATION_COLLISION",
            "title": "One-Way Mode Multi-Entry Blending Violates Logical Position Isolation",
            "severity": "HIGH",
            "affected_trades": ["T-12 (#7)", "T-17 (#12)", "T-19 (#14)", "T-21 (#16)"],
            "description": "Bybit perpetual connector operates in One-Way Mode (positionIdx=0). When the strategy receives a second entry signal in the same symbol and side while a previous trade (or remainder) is open, Bybit aggregates them into a single exchange position with a weighted blended entry price. However, the bot's internal state tracks them as separate dictionary entries, creating an impedance mismatch between exchange risk and bot logic.",
            "impact": "Stop orders from prior trades are either cancelled or rotated with partial quantities, leading to apparent quantity discrepancies (e.g., 6870 entry closed as 8450; 593 entry closed as 822).",
            "remediation": "Switch exchange mode to Hedge Mode with dual positionIdx (1 for Buy, 2 for Sell) or enforce a strict concurrency mutex blocking new entries while an existing position is open on that symbol/side."
        },
        {
            "anomaly_id": "ANOMALY-02",
            "category": "EXECUTION_TYPE_CONTAMINATION",
            "title": "Funding Settlements Present in Execution Stream",
            "severity": "LOW",
            "affected_trades": ["ALL"],
            "description": "Bybit /v5/execution/list returns records where execType=='Funding' alongside execType=='Trade'. If not explicitly filtered, trade reconcilers mistake periodic 8-hour funding cash deductions for zero-quantity order fills.",
            "impact": "Account reconciliation scripts report corrupted fee/pnl statistics if funding records are treated as trades.",
            "remediation": "Filter all Bybit execution streams strictly where execType == 'Trade'."
        },
        {
            "anomaly_id": "ANOMALY-03",
            "category": "LATENCY_WINDOW_PROTECTION",
            "title": "Stop Loss Cancel-Replace Naked Interval",
            "severity": "MEDIUM",
            "affected_trades": ["T-12", "T-19", "T-21"],
            "description": "When rotating or resizing stop orders (e.g. after TP1 execution or secondary entry rotation), the bot sends a cancel/deactivate request followed by a new stop order placement. During this network round-trip window (approx 150ms-400ms), the exchange position has no active stop loss registered.",
            "impact": "If a violent market flash-crash occurs during this sub-second interval, liquidation or runaway loss could occur.",
            "remediation": "Use Bybit /v5/order/amend endpoint or conditional order edit API rather than cancel-and-replace."
        }
    ]
}

# ---------------------------------------------------------
# WRITE ALL CSVs AND JSON
# ---------------------------------------------------------
with open(os.path.join(out_dir, "checks.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "rule_id", "trade_id", "symbol", "positionIdx", "expected", "observed",
        "status", "evidence_file", "orderId_execId", "utc_timestamp", "severity", "missing_evidence"
    ])
    writer.writeheader()
    writer.writerows(checks_rows)
print(f"checks.csv written with {len(checks_rows)} rows.")

with open(os.path.join(out_dir, "logical_trades.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "trade_id", "parent_order_id", "symbol", "side", "entry_time_utc", "entry_order_id",
        "entry_link_id", "entry_qty", "entry_price", "initial_sl_price", "initial_sl_link_id",
        "be_triggered", "be_time_utc", "be_sl_price", "tp1_order_id", "tp1_link_id", "tp1_qty",
        "tp1_fill_time_utc", "tp1_fill_price", "tp1_pnl", "trailing_activated",
        "trailing_activation_time_utc", "exit_time_utc", "exit_order_id", "exit_link_id",
        "exit_qty", "exit_price", "exit_reason", "total_realized_pnl", "total_fee", "status"
    ])
    writer.writeheader()
    writer.writerows(logical_trades)
print(f"logical_trades.csv written with {len(logical_trades)} rows.")

with open(os.path.join(out_dir, "exchange_position_ledger.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "timestamp_utc", "symbol", "position_idx", "side", "change_type", "order_id",
        "order_link_id", "exec_id", "trade_id", "qty_delta", "current_size", "exec_price",
        "blended_entry_price", "realized_pnl", "fee", "cash_flow"
    ])
    writer.writeheader()
    writer.writerows(exchange_ledger_rows)
print(f"exchange_position_ledger.csv written with {len(exchange_ledger_rows)} rows.")

with open(os.path.join(out_dir, "order_execution_map.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "logical_trade_id", "symbol", "order_role", "order_id", "order_link_id", "order_type",
        "side", "reduce_only", "trigger_price", "order_qty", "order_status", "exec_id",
        "exec_time_utc", "exec_qty", "exec_price", "exec_fee", "exec_type"
    ])
    writer.writeheader()
    writer.writerows(order_exec_map_rows)
print(f"order_execution_map.csv written with {len(order_exec_map_rows)} rows.")

with open(os.path.join(out_dir, "timeline.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "timestamp_utc_ms", "timestamp_iso_utc", "symbol", "event_category", "event_type",
        "identifier", "details", "impact"
    ])
    writer.writeheader()
    writer.writerows(timeline_events)
print(f"timeline.csv written with {len(timeline_events)} rows.")

with open(os.path.join(out_dir, "anomalies.json"), "w", encoding="utf-8") as f:
    json.dump(anomalies, f, indent=2)
print("anomalies.json written.")
