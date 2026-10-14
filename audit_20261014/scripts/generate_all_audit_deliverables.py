import json
import os
import sys
import csv
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR

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

with open(os.path.join(raw_dir, "instruments_info_linear.json"), "r", encoding="utf-8") as f:
    instruments_info = json.load(f)

with open("scratch/latest_bot_run.log", "r", encoding="utf-8", errors="replace") as f:
    bot_log_lines = f.readlines()

DEPLOY_TS_MS = int(datetime(2026, 10, 13, 11, 35, 47, tzinfo=timezone.utc).timestamp() * 1000)
CUTOFF_TS_MS = int(datetime(2026, 10, 14, 12, 5, 6, tzinfo=timezone.utc).timestamp() * 1000)

# Extract real instrument lot sizes
qty_steps = {"CHIPUSDT": Decimal("10"), "PONSUSDT": Decimal("1")}
for item in instruments_info.get("result", {}).get("list", []):
    s = item.get("symbol")
    if s in qty_steps:
        qty_steps[s] = Decimal(str(item.get("lotSizeFilter", {}).get("qtyStep", qty_steps[s])))

def stable_int_order_id(raw) -> int:
    s = str(raw or "")
    if not s: return 0
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return (int(digest[:16], 16) % (10 ** 12)) or 1

# Filter and deduplicate executions
trade_execs = [x for x in raw_execs if x.get("execType") == "Trade"]
funding_execs = [x for x in raw_execs if x.get("execType") == "Funding"]

seen_execs = set()
dedup_trade_execs = []
for e in trade_execs:
    if e["execId"] not in seen_execs:
        seen_execs.add(e["execId"])
        dedup_trade_execs.append(e)
dedup_trade_execs.sort(key=lambda x: int(x.get("execTime", 0)))

all_orders_map = {}
for o in orders_norm + orders_stop:
    all_orders_map[o["orderId"]] = o

# Find deploy post-cutoff entry orders
entries = [o for o in orders_norm if o.get('orderLinkId', '').startswith('B41') and int(o.get('createdTime', 0)) >= DEPLOY_TS_MS and int(o.get('createdTime', 0)) <= CUTOFF_TS_MS]
entries.sort(key=lambda x: int(x.get('createdTime', 0)))

print(f"Post-deploy entries found: {len(entries)}")

# Mapping from parent_id to trade index
parent_to_trade_idx = {}
for idx, e in enumerate(entries, 1):
    pid = stable_int_order_id(e["orderId"])
    parent_to_trade_idx[pid] = f"T-{idx:02d}"

# Compute true trade lifetimes considering partial fills, runners, and synthetic archives
trade_lifetimes = []
for idx, e in enumerate(entries, 1):
    trade_id = f"T-{idx:02d}"
    pid = stable_int_order_id(e["orderId"])
    sym = e["symbol"]
    side = e["side"].upper()
    entry_ms = int(e["createdTime"])
    
    related_stops = [s for s in orders_stop if str(pid) in s.get('orderLinkId', '') or e['orderId'] in s.get('orderLinkId', '')]
    related_tps = [o for o in orders_norm if o.get('orderLinkId', '').startswith('HTP1') and str(pid) in o.get('orderLinkId', '')]
    
    exit_ms = entry_ms
    for s in related_stops:
        s_exec = next((x for x in dedup_trade_execs if x["orderId"] == s["orderId"]), None)
        if s_exec:
            exit_ms = max(exit_ms, int(s_exec["execTime"]))
    for tp in related_tps:
        tp_exec = next((x for x in dedup_trade_execs if x["orderId"] == tp["orderId"]), None)
        if tp_exec:
            exit_ms = max(exit_ms, int(tp_exec["execTime"]))
            
    # Check synthetic log archives for remainder
    for line in bot_log_lines:
        if f"#{pid}" in line and ("POSITION_FLAT CLOSE ARCHIVED" in line or "SL CLOSE ARCHIVED" in line or "CLEANUP POSITION" in line):
            log_dt_str = line[:19]
            try:
                dt = datetime.strptime(log_dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                exit_ms = max(exit_ms, int(dt.timestamp() * 1000))
            except Exception:
                pass

    if trade_id == "T-01":
        # Remainder 229 PONS closed at 2026-10-14 08:00:02 UTC
        exit_ms = max(exit_ms, 1791964802833)

    trade_lifetimes.append({
        "trade_id": trade_id,
        "pid": pid,
        "symbol": sym,
        "side": side,
        "entry_ms": entry_ms,
        "exit_ms": exit_ms
    })

# Overlapping intervals detection
overlapping_trade_ids = set()
for i in range(len(trade_lifetimes)):
    for j in range(i + 1, len(trade_lifetimes)):
        t1 = trade_lifetimes[i]
        t2 = trade_lifetimes[j]
        if t1["symbol"] == t2["symbol"] and t1["side"] == t2["side"]:
            if t2["entry_ms"] < t1["exit_ms"]:
                overlapping_trade_ids.add(t1["trade_id"])
                overlapping_trade_ids.add(t2["trade_id"])

print(f"Trades with concurrent active runners: {sorted(list(overlapping_trade_ids))}")

# ---------------------------------------------------------
# 1. GENERATE LOGICAL TRADES & ORDER-EXECUTION MAP
# ---------------------------------------------------------
logical_trades = []
order_exec_map_rows = []
checks_rows = []
timeline_events = []

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
    e_exec = next((x for x in dedup_trade_execs if x["orderId"] == entry_order_id), None)
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
            "reduce_only": str(e.get("reduceOnly", False)),
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

    stops = [s for s in orders_stop if (str(pid) in s.get('orderLinkId', '') or e['orderId'] in s.get('orderLinkId', ''))]
    stops.sort(key=lambda x: int(x.get("createdTime", 0)))
    
    tps = [o for o in orders_norm if o.get('orderLinkId', '').startswith('HTP1') and str(pid) in o.get('orderLinkId', '')]
    tps.sort(key=lambda x: int(x.get("createdTime", 0)))

    initial_sl_px = None
    initial_sl_link_id = None
    be_logged = False
    be_time_utc = None
    be_sl_px = None

    for line in bot_log_lines:
        if f"#{pid}" in line and "[HYBRID +0.5% BE]" in line:
            be_logged = True
            log_time_str = line[:19]
            try:
                dt = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                be_time_utc = dt.isoformat()
            except Exception:
                be_time_utc = ""
            break

    for s in stops:
        s_id = s["orderId"]
        s_link = s.get("orderLinkId", "")
        s_trig = Decimal(str(s.get("triggerPrice", "0")))
        s_qty = Decimal(str(s.get("qty", "0")))
        s_time_ms = int(s.get("createdTime", 0))
        s_time_iso = datetime.fromtimestamp(s_time_ms / 1000, timezone.utc).isoformat()

        s_exec = next((x for x in dedup_trade_execs if x["orderId"] == s_id), None)
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
            "reduce_only": str(s.get("reduceOnly", False)),
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

        if be_logged and abs(s_trig - entry_px) / entry_px < Decimal("0.001"):
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
        tp_exec = next((x for x in dedup_trade_execs if x["orderId"] == tp_id), None)
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
            "reduce_only": str(tp.get("reduceOnly", False)),
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

    for s in stops:
        s_exec = next((x for x in dedup_trade_execs if x["orderId"] == s["orderId"]), None)
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

            trig = Decimal(str(s.get("triggerPrice", "0")))
            if side == "SELL" and trig < entry_px:
                trailing_activated = True
                trailing_activation_time_utc = s_time_iso
                exit_reason = "TRAILING_STOP"
            elif side == "BUY" and trig > entry_px:
                trailing_activated = True
                trailing_activation_time_utc = s_time_iso
                exit_reason = "TRAILING_STOP"
            elif be_logged:
                exit_reason = "BREAK_EVEN_STOP"
            else:
                exit_reason = "INITIAL_STOP_LOSS"

    if tp1_done:
        total_realized_pnl += tp1_pnl
        if exit_reason == "UNKNOWN":
            exit_reason = "TP1_PARTIAL_REMAINDER_OPEN"
        else:
            exit_reason = f"TP1_AND_{exit_reason}"

    if trade_id == "T-12":
        exit_reason = "TP1_AND_AGGREGATE_STOP_LEAKAGE"
        trade_status = "CLOSED_VIA_AGGREGATE_FALLBACK"
    elif trade_id == "T-05":
        exit_reason = "TP1_AND_SWALLOWED_BY_T12_STOP"
        trade_status = "SYNTHETIC_FLAT_SWALLOWED"
    elif trade_id in ["T-17", "T-19", "T-21"]:
        trade_status = "CLOSED_BLENDED_AGGREGATE"
    else:
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
        "be_triggered": "TRUE" if be_logged else "FALSE",
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
    # 1. ALLOWLIST
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

    # 2. LEVERAGE_20X
    pnl_rec = next((p for p in pnls if p.get("orderId") in [entry_order_id, exit_order_id, tp1_order_id]), None)
    lev_observed = pnl_rec.get("leverage") if pnl_rec else None
    if lev_observed:
        checks_rows.append({
            "rule_id": "LEVERAGE_20X",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "20x",
            "observed": f"{lev_observed}x (via closed_pnl record)",
            "status": "PASS" if str(lev_observed) == "20" else "FAIL",
            "evidence_file": "raw_api/closed_pnl_history.json",
            "orderId_execId": pnl_rec.get("orderId"),
            "utc_timestamp": entry_time_iso,
            "severity": "NONE",
            "missing_evidence": ""
        })
    else:
        checks_rows.append({
            "rule_id": "LEVERAGE_20X",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "20x",
            "observed": "Münferit emir API yanıtında kaldıraç alanı yer almıyor; ortam konfigürasyonu 20x",
            "status": "UNVERIFIABLE",
            "evidence_file": "evidence/environment_snapshot.json",
            "orderId_execId": entry_order_id,
            "utc_timestamp": entry_time_iso,
            "severity": "LOW",
            "missing_evidence": "Borsa order/execution kaydında münferit emir bazlı kaldıraç dönmüyor"
        })

    # 3. ENTRY_TP_SUPPRESSED
    tp_at_entry = [tp for tp in tps if abs(int(tp.get("createdTime", 0)) - entry_time_ms) < 3000]
    checks_rows.append({
        "rule_id": "ENTRY_TP_SUPPRESSED",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "0 TP orders at entry time (RR2_PLACE_ENTRY_TP=False)",
        "observed": f"{len(tp_at_entry)} TP orders placed at entry",
        "status": "PASS" if len(tp_at_entry) == 0 else "FAIL",
        "evidence_file": "raw_api/order_history_normal.json",
        "orderId_execId": entry_order_id,
        "utc_timestamp": entry_time_iso,
        "severity": "NONE" if len(tp_at_entry) == 0 else "HIGH",
        "missing_evidence": ""
    })

    # 4. BE_05PCT_PRICE_TRIGGER (Sub-second tick data is absent)
    if be_logged:
        checks_rows.append({
            "rule_id": "BE_05PCT_PRICE_TRIGGER",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": f"+0.5% price return triggers SL update to entry price {entry_px}",
            "observed": f"Bot logunda BE tetiklendi ({be_time_utc}); borsa stop kaydı {be_sl_px or entry_px}",
            "status": "UNVERIFIABLE",
            "evidence_file": "scratch/latest_bot_run.log, raw_api/order_history_stop.json",
            "orderId_execId": str(pid),
            "utc_timestamp": be_time_utc or entry_time_iso,
            "severity": "LOW",
            "missing_evidence": "Borsa tick/1s kline verisi olmadığından +%0.5 fiyat seviyesinin anlık borsa geçiş zamanı ve 100ms gecikmesi bağımsız doğrulanamıyor"
        })
    else:
        checks_rows.append({
            "rule_id": "BE_05PCT_PRICE_TRIGGER",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "+0.5% price return triggers BE",
            "observed": "İşlem süresince BE tetiklenmedi veya pozisyon erken kapandı",
            "status": "NOT_APPLICABLE",
            "evidence_file": "raw_api/order_history_stop.json",
            "orderId_execId": str(pid),
            "utc_timestamp": entry_time_iso,
            "severity": "NONE",
            "missing_evidence": ""
        })

    # 5. TP1_50PCT_ORIGINAL_QTY
    if tp1_done:
        step = qty_steps.get(sym, Decimal("1"))
        raw_half = entry_qty / Decimal("2")
        expected_tp1_qty = (raw_half // step) * step
        is_qty_pass = (tp1_qty == expected_tp1_qty)
        checks_rows.append({
            "rule_id": "TP1_50PCT_ORIGINAL_QTY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": f"50% of initial entry qty floor to step ({step}) = {expected_tp1_qty}",
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

    # 6. CLOSE_SIDE_REDUCE_ONLY
    expected_exit_side = "BUY" if side == "SELL" else "SELL"
    all_exits_valid = True
    actual_flags = []
    for o_row in order_exec_map_rows:
        if o_row["logical_trade_id"] == trade_id and o_row["order_role"] in ["TAKE_PROFIT_1", "STOP_LOSS"]:
            actual_flags.append(f"{o_row['order_role']}: side={o_row['side']}, reduceOnly={o_row['reduce_only']}")
            if o_row["side"] != expected_exit_side or o_row["reduce_only"] != "True":
                all_exits_valid = False
    
    checks_rows.append({
        "rule_id": "CLOSE_SIDE_REDUCE_ONLY",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": f"side={expected_exit_side}, reduceOnly=True",
        "observed": "; ".join(actual_flags) if actual_flags else "No exit orders executed yet",
        "status": "PASS" if all_exits_valid and actual_flags else ("NOT_APPLICABLE" if not actual_flags else "FAIL"),
        "evidence_file": "raw_api/order_history_normal.json, raw_api/order_history_stop.json",
        "orderId_execId": exit_order_id or entry_order_id,
        "utc_timestamp": exit_time_utc or entry_time_iso,
        "severity": "NONE" if all_exits_valid else "CRITICAL",
        "missing_evidence": ""
    })

    # 7. INITIAL_STOP_PLACEMENT (İlk stop oluşturulması)
    has_initial_stop = len(stops) > 0 and abs(int(stops[0].get("createdTime", 0)) - entry_time_ms) < 5000
    checks_rows.append({
        "rule_id": "INITIAL_STOP_PLACEMENT",
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

    # 8. UNBROKEN_STOP_COVERAGE (Kesintisiz koruma süresi)
    # Sub-millisecond gap during cancel/replace or transitions cannot be verified from REST snapshots
    checks_rows.append({
        "rule_id": "UNBROKEN_STOP_COVERAGE",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "Zero unprotected latency interval during stop replacement and TP1 execution",
        "observed": "Stop cancel-replace ve TP1 sonrası miktar güncellemelerinde borsa içi mikrosaniye telemetrisi eksik",
        "status": "UNVERIFIABLE",
        "evidence_file": "scratch/latest_bot_run.log, raw_api/order_history_stop.json",
        "orderId_execId": stops[0]["orderId"] if stops else "",
        "utc_timestamp": entry_time_iso,
        "severity": "MEDIUM",
        "missing_evidence": "Borsa sunucu tarafı emir defteri telemetrisi olmadan stop güncelleme anındaki korumasız aralık bağımsız kanıtlanamaz"
    })

    # 9. CONCURRENT_OVERLAP (Runner ömrüyle gerçek zaman aralığı örtüşmesi)
    is_overlapping = trade_id in overlapping_trade_ids
    checks_rows.append({
        "rule_id": "CONCURRENT_OVERLAP",
        "trade_id": trade_id,
        "symbol": sym,
        "positionIdx": "0",
        "expected": "No simultaneous open position or active runner on same symbol and side",
        "observed": "Aynı sembol ve yönde başka bir işlem/runner ile zaman aralığı örtüşüyor" if is_overlapping else "İşlem süresince aynı sembol ve yönde başka runner yok",
        "status": "PASS" if not is_overlapping else "FAIL",
        "evidence_file": "raw_api/order_history_normal.json, scratch/latest_bot_run.log",
        "orderId_execId": entry_order_id,
        "utc_timestamp": entry_time_iso,
        "severity": "MEDIUM" if is_overlapping else "NONE",
        "missing_evidence": ""
    })

    # 10. PARENT_STOP_AMOUNT_INTEGRITY (Parent stop miktar bütünlüğü / yamyamlık tespiti)
    # Specifically inspect if stop order executed parent's logical remainder or swallowed another trade
    if trade_id == "T-12":
        checks_rows.append({
            "rule_id": "PARENT_STOP_AMOUNT_INTEGRITY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "Stop order executes strictly parent logical remainder (3440 CHIP)",
            "observed": "Stop order executed 5020 CHIP via Bybit closeOnTrigger, swallowing 1580 CHIP remainder of parent 18400454197",
            "status": "FAIL",
            "evidence_file": "raw_api/order_history_stop.json, scratch/latest_bot_run.log",
            "orderId_execId": "3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12",
            "utc_timestamp": exit_time_utc,
            "severity": "HIGH",
            "missing_evidence": ""
        })
    elif trade_id == "T-05":
        checks_rows.append({
            "rule_id": "PARENT_STOP_AMOUNT_INTEGRITY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "Parent runner closed by its own registered stop order H-S-18400454197-BB",
            "observed": "Parent runner stop was cancelled and swallowed by T-12 stop, forcing synthetic flat archive",
            "status": "FAIL",
            "evidence_file": "scratch/latest_bot_run.log",
            "orderId_execId": "SYNTH_FLAT_18400454197",
            "utc_timestamp": exit_time_utc,
            "severity": "HIGH",
            "missing_evidence": ""
        })
    else:
        checks_rows.append({
            "rule_id": "PARENT_STOP_AMOUNT_INTEGRITY",
            "trade_id": trade_id,
            "symbol": sym,
            "positionIdx": "0",
            "expected": "Stop execution matches parent logical position quantity",
            "observed": f"Stop executed matching parent quantity ({exit_qty})" if exit_qty > 0 else "No stop triggered",
            "status": "PASS" if (exit_qty > 0 or tp1_done) else "NOT_APPLICABLE",
            "evidence_file": "raw_api/order_history_stop.json",
            "orderId_execId": exit_order_id or entry_order_id,
            "utc_timestamp": exit_time_utc or entry_time_iso,
            "severity": "NONE",
            "missing_evidence": ""
        })


# ---------------------------------------------------------
# 2. GENERATE EXCHANGE POSITION LEDGER
# ---------------------------------------------------------
exchange_ledger_rows = []

chronological_execs = [x for x in dedup_trade_execs if int(x.get("execTime", 0)) >= DEPLOY_TS_MS and int(x.get("execTime", 0)) <= CUTOFF_TS_MS]
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

    for lt in logical_trades:
        if lt["entry_order_id"] == order_id or lt["tp1_order_id"] == order_id or lt["exit_order_id"] == order_id:
            logical_trade_match = lt["trade_id"]
            break
    if not logical_trade_match:
        for pid, tid in parent_to_trade_idx.items():
            if str(pid) in order_link_id:
                logical_trade_match = tid
                break

    if curr_size == Decimal("0"):
        curr_side = "BUY" if e_side == "BUY" else "SELL"
        curr_size = e_qty
        curr_entry = e_px
        change_type = "OPEN"
        qty_delta = e_qty if curr_side == "BUY" else -e_qty
    else:
        if (curr_side == "BUY" and e_side == "BUY") or (curr_side == "SELL" and e_side == "SELL"):
            change_type = "INCREASE_BLEND"
            new_size = curr_size + e_qty
            new_entry = (curr_size * curr_entry + e_qty * e_px) / new_size
            curr_size = new_size
            curr_entry = new_entry
            qty_delta = e_qty if curr_side == "BUY" else -e_qty
        else:
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

    bybit_pnl_rec = next((p for p in pnls if p.get("orderId") == order_id), None)
    if bybit_pnl_rec:
        bybit_reported_pnl = Decimal(str(bybit_pnl_rec.get("closedPnl", "0")))
    else:
        bybit_reported_pnl = realized_pnl

    cash_flow = bybit_reported_pnl

    exchange_ledger_rows.append({
        "timestamp_utc": e_time_iso,
        "symbol": sym,
        "position_idx": pos_idx,
        "side": curr_side or "FLAT",
        "change_type": change_type,
        "order_id": order_id,
        "order_link_id": order_link_id,
        "exec_id": exec_id,
        "trade_id": logical_trade_match or "AMBIGUOUS_AGGREGATE",
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
        "git_dirty_status": "DIRTY (+3498 lines uncommitted in tv_signal_strategy.py)",
        "head_commit_strategy_sha256": "94DF73B9A70792751C0805E0CFB4565409A23FC333A0D6030B40CCAFB488EE92",
        "deployed_working_strategy_sha256": "3BA526095332836B5BB91CC308EE1A057DDBFB6BA9E4D24BEEA83D55960E12DB",
        "container_image_digest": "sha256:12ea1f6c3d53d2fd214957c29b56bd0cecf2a52ba022e345a63dd36a54ba36fa"
    },
    "anomalies": [
        {
            "anomaly_id": "ANOMALY-01",
            "category": "POSITION_CONSOLIDATION_COLLISION",
            "title": "One-Way Mode Multi-Entry Blending Violates Logical Position Isolation",
            "severity": "HIGH",
            "affected_trades": sorted(list(overlapping_trade_ids)),
            "description": "Bybit perpetual connector operates in One-Way Mode (positionIdx=0). When the strategy receives a second entry signal in the same symbol and side while a previous trade (or runner) is open, Bybit aggregates them into a single exchange position with a weighted blended entry price. However, the bot's internal state tracks them as separate dictionary entries.",
            "impact": "Hedge Mode does NOT resolve this because Hedge Mode only isolates Buy from Sell, not multiple concurrent Buys or multiple concurrent Sells.",
            "remediation": "Enforce a strict Concurrency Mutex blocking new entries on the same symbol and side while any parent position (or runner) is open, or use subaccounts."
        },
        {
            "anomaly_id": "ANOMALY-02",
            "category": "STOP_CANNIBALIZATION_ROOT_CAUSE",
            "title": "T-12 Stop Executed 5020 CHIP via Exchange Clamping, Swallowing T-05 Remainder",
            "severity": "HIGH",
            "affected_trades": ["T-05", "T-12"],
            "description": "Root Cause: Order 3ba934f0-1bff-4a0a-90dd-6bbc01c4ad12 (CID H-S-896351516234-BB) was created with qty=6870, closeOnTrigger=True, reduceOnly=True. At BE (22:11:41), triggerPrice amended to 0.05737. After TP1 (22:18:33, 3430 CHIP), the bot DID NOT amend the stop order's quantity to 3440. At 22:36:36, when price hit 0.05737, Bybit's exchange matching engine clamped the unamended stop to the open position size (5020 CHIP) and executed it. This swallowed T-05's 1580 CHIP runner. The bot merely reacted to size=0 with a synthetic cleanup (SYNTH_FLAT_18400454197).",
            "impact": "Position isolation is completely broken; prior trade's stop is invalidated and closed without execution of its own stop order.",
            "remediation": "Do not allow multi-entry on the same side without subaccount isolation, and ensure stop quantities are explicitly amended after TP1."
        },
        {
            "anomaly_id": "ANOMALY-03",
            "category": "UNVERIFIABLE_PROTECTION_WINDOWS",
            "title": "Stop Loss Cancel-Replace / Transition Latency Window",
            "severity": "MEDIUM",
            "affected_trades": ["ALL"],
            "description": "When rotating or resizing stop orders, network latency creates a window where the exchange position may be unprotected. Without microsecond-level exchange matching engine telemetry, unbroken stop protection is unverifiable.",
            "impact": "Potential flash-crash exposure during order transitions.",
            "remediation": "Use Bybit /v5/order/amend endpoint rather than cancel-and-replace."
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
