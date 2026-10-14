import json
from datetime import datetime, timezone
import hashlib

with open('audit_20261014/raw_api/order_history_normal.json', 'r', encoding='utf-8') as f:
    orders_norm = json.load(f)
with open('audit_20261014/raw_api/order_history_stop.json', 'r', encoding='utf-8') as f:
    orders_stop = json.load(f)
with open('audit_20261014/raw_api/execution_list_history.json', 'r', encoding='utf-8') as f:
    execs = [x for x in json.load(f) if x.get('execType') == 'Trade']
with open('scratch/latest_bot_run.log', 'r', encoding='utf-8', errors='replace') as f:
    bot_log_lines = f.readlines()

DEPLOY_TS_MS = int(datetime(2026, 10, 13, 11, 35, 47, tzinfo=timezone.utc).timestamp() * 1000)
CUTOFF_TS_MS = int(datetime(2026, 10, 14, 12, 5, 6, tzinfo=timezone.utc).timestamp() * 1000)

def stable_int_order_id(raw) -> int:
    s = str(raw or "")
    if not s: return 0
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return (int(digest[:16], 16) % (10 ** 12)) or 1

entries = [o for o in orders_norm if o.get('orderLinkId', '').startswith('B41') and int(o.get('createdTime', 0)) >= DEPLOY_TS_MS and int(o.get('createdTime', 0)) <= CUTOFF_TS_MS]
entries.sort(key=lambda x: int(x.get('createdTime', 0)))

print(f"Total post-deploy entries: {len(entries)}")

# True lifetime calculation
lifetimes = []
for idx, e in enumerate(entries, 1):
    trade_id = f"T-{idx:02d}"
    pid = stable_int_order_id(e["orderId"])
    sym = e["symbol"]
    side = e["side"].upper()
    entry_ms = int(e["createdTime"])
    entry_iso = datetime.fromtimestamp(entry_ms/1000, timezone.utc).isoformat()
    
    # Check all related orders and executions
    related_stops = [s for s in orders_stop if str(pid) in s.get('orderLinkId', '') or e['orderId'] in s.get('orderLinkId', '')]
    related_tps = [o for o in orders_norm if o.get('orderLinkId', '').startswith('HTP1') and str(pid) in o.get('orderLinkId', '')]
    
    # Initial exit_ms is entry_ms
    exit_ms = entry_ms
    exit_events = []
    
    # Check stop executions
    for s in related_stops:
        s_exec = next((x for x in execs if x["orderId"] == s["orderId"]), None)
        if s_exec:
            t_exec = int(s_exec["execTime"])
            exit_ms = max(exit_ms, t_exec)
            exit_events.append((t_exec, f"Stop exec {s_exec['execQty']} @ {s_exec['execPrice']}"))
            
    # Check TP executions
    for tp in related_tps:
        tp_exec = next((x for x in execs if x["orderId"] == tp["orderId"]), None)
        if tp_exec:
            t_exec = int(tp_exec["execTime"])
            exit_ms = max(exit_ms, t_exec)
            exit_events.append((t_exec, f"TP1 exec {tp_exec['execQty']} @ {tp_exec['execPrice']}"))

    # Check synthetic log archives for remainder
    for line in bot_log_lines:
        if f"#{pid}" in line and ("POSITION_FLAT CLOSE ARCHIVED" in line or "SL CLOSE ARCHIVED" in line or "CLEANUP POSITION" in line):
            log_dt_str = line[:19]
            try:
                dt = datetime.strptime(log_dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                t_log = int(dt.timestamp() * 1000)
                exit_ms = max(exit_ms, t_log)
                exit_events.append((t_log, f"Bot log archive: {line.strip()[:60]}"))
            except Exception:
                pass
                
    # Special known runners:
    # T-01: remainder 229 PONS was finally closed at 2026-10-14 08:00:02 UTC by bdb1eec4 (H-S-812222892888-BB1)
    if trade_id == "T-01":
        # bdb1eec4 exec time
        t_rem = 1791964802833
        exit_ms = max(exit_ms, t_rem)
        exit_events.append((t_rem, "Runner closed by rotated stop bdb1eec4"))
        
    exit_iso = datetime.fromtimestamp(exit_ms/1000, timezone.utc).isoformat()
    lifetimes.append({
        "trade_id": trade_id,
        "pid": pid,
        "symbol": sym,
        "side": side,
        "entry_ms": entry_ms,
        "entry_iso": entry_iso,
        "exit_ms": exit_ms,
        "exit_iso": exit_iso,
        "duration_min": round((exit_ms - entry_ms) / 60000, 1),
        "events": exit_events
    })

print("\n=== TRUE TRADE LIFETIMES (ENTRY TO FULL CLOSURE) ===")
for lt in lifetimes:
    print(f"{lt['trade_id']}: {lt['symbol']} {lt['side']} | Entry: {lt['entry_iso']} -> Exit: {lt['exit_iso']} ({lt['duration_min']} min)")
