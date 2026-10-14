import json
from datetime import datetime, timezone
from decimal import Decimal

with open("audit_20261014/raw_api/execution_list_history.json", "r", encoding="utf-8") as f:
    execs = json.load(f)

with open("audit_20261014/raw_api/closed_pnl_history.json", "r", encoding="utf-8") as f:
    pnls = json.load(f)

with open("audit_20261014/raw_api/order_history_normal.json", "r", encoding="utf-8") as f:
    orders_norm = json.load(f)

with open("audit_20261014/raw_api/order_history_stop.json", "r", encoding="utf-8") as f:
    orders_stop = json.load(f)

pons_execs = [x for x in execs if x.get("symbol") == "PONSUSDT"]
pons_execs.sort(key=lambda x: int(x.get("execTime", 0)))

print("=== ALL PONS EXECUTIONS (CHRONOLOGICAL) ===")
for x in pons_execs:
    t = datetime.fromtimestamp(int(x['execTime'])/1000, timezone.utc).isoformat()
    print(f"[{t}] Type={x.get('execType')} | Side={x['side']} | Qty={x['execQty']} | Px={x['execPrice']} | OrderId={x['orderId']} | LinkId={x.get('orderLinkId')} | Fee={x.get('execFee')}")

pons_pnls = [x for x in pnls if x.get("symbol") == "PONSUSDT"]
pons_pnls.sort(key=lambda x: int(x.get("updatedTime", 0)))

print("\n=== ALL PONS CLOSED PNL (CHRONOLOGICAL) ===")
for p in pons_pnls:
    t = datetime.fromtimestamp(int(p['updatedTime'])/1000, timezone.utc).isoformat()
    print(f"[{t}] OrderId={p['orderId']} | Side={p['side']} | Qty={p['qty']} | EntryPx={p['avgEntryPrice']} | ExitPx={p['avgExitPrice']} | PnL={p['closedPnl']}")
