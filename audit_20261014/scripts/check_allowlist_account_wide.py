import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

raw_dir = "audit_20261014/raw_api"

with open(os.path.join(raw_dir, "execution_list_history.json"), "r", encoding="utf-8") as f:
    execs = json.load(f)

with open(os.path.join(raw_dir, "order_history_normal.json"), "r", encoding="utf-8") as f:
    orders_norm = json.load(f)

with open(os.path.join(raw_dir, "order_history_stop.json"), "r", encoding="utf-8") as f:
    orders_stop = json.load(f)

with open(os.path.join(raw_dir, "closed_pnl_history.json"), "r", encoding="utf-8") as f:
    pnl = json.load(f)

deploy_ts_ms = 1791891347000 # 2026-10-13 11:35:47 UTC

all_symbols_exec = set(e["symbol"] for e in execs if int(e.get("execTime", 0)) >= deploy_ts_ms)
all_symbols_orders_norm = set(o["symbol"] for o in orders_norm if int(o.get("createdTime", 0)) >= deploy_ts_ms)
all_symbols_orders_stop = set(s["symbol"] for s in orders_stop if int(s.get("createdTime", 0)) >= deploy_ts_ms)
all_symbols_pnl = set(p["symbol"] for p in pnl if int(p.get("updatedTime", 0)) >= deploy_ts_ms)

print("Account-wide symbols observed since deploy (2026-10-13 11:35:47 UTC):")
print(" - Executions:", all_symbols_exec)
print(" - Normal Orders:", all_symbols_orders_norm)
print(" - Stop Orders:", all_symbols_orders_stop)
print(" - Closed PnL:", all_symbols_pnl)

combined_symbols = all_symbols_exec | all_symbols_orders_norm | all_symbols_orders_stop | all_symbols_pnl
print("Combined symbols observed:", combined_symbols)

unpermitted = [s for s in combined_symbols if s not in ("CHIPUSDT", "PONSUSDT")]
print("Unpermitted symbols found:", unpermitted)
