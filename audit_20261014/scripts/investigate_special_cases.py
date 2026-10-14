import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

sys.stdout.reconfigure(encoding="utf-8")

raw_dir = "audit_20261014/raw_api"

with open(os.path.join(raw_dir, "execution_list_history.json"), "r", encoding="utf-8") as f:
    execs = json.load(f)

with open(os.path.join(raw_dir, "order_history_normal.json"), "r", encoding="utf-8") as f:
    orders_norm = json.load(f)

with open(os.path.join(raw_dir, "order_history_stop.json"), "r", encoding="utf-8") as f:
    orders_stop = json.load(f)

with open(os.path.join(raw_dir, "closed_pnl_history.json"), "r", encoding="utf-8") as f:
    pnls = json.load(f)

with open("scratch/latest_bot_run.log", "r", encoding="utf-8", errors="replace") as f:
    log_lines = f.readlines()

def stable_int_order_id(raw) -> int:
    s = str(raw or "")
    if not s: return 0
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return (int(digest[:16], 16) % (10 ** 12)) or 1

# Let's inspect all orders chronologically
all_orders = orders_norm + orders_stop
all_orders.sort(key=lambda x: int(x.get("createdTime", 0)))

print("=== SPECIAL CASE INVESTIGATION ===")

# ----------------------------------------------------
# CASE 1: #7 (CHIP SHORT around 2026-10-13 22:00:23 UTC)
# Entry 6870 CHIP, apparent total close 8450 CHIP
# ----------------------------------------------------
print("\n" + "="*80)
print("CASE 1: Pos #7 - CHIP SHORT (2026-10-13 ~22:00 UTC)")
print("="*80)

# Find entry orders around 22:00
for o in all_orders:
    t = datetime.fromtimestamp(int(o["createdTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if "2026-10-13 21:" in t or "2026-10-13 22:" in t:
        if o["symbol"] == "CHIPUSDT":
            print(f"[{t} UTC] OrderId={o['orderId']} | LinkId={o.get('orderLinkId')} | Side={o['side']} | Qty={o['qty']} | Status={o['orderStatus']} | Type={o['orderType']} | ReduceOnly={o.get('reduceOnly')} | TrigPx={o.get('triggerPrice')}")

# Find executions around 22:00 to 22:45
print("\nExecutions around 21:50 - 22:45:")
for e in execs:
    t = datetime.fromtimestamp(int(e["execTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if ("2026-10-13 21:5" in t or "2026-10-13 22:" in t) and e["symbol"] == "CHIPUSDT":
        print(f"[{t} UTC] ExecId={e['execId']} | OrderId={e['orderId']} | LinkId={e.get('orderLinkId')} | Side={e['side']} | Qty={e['execQty']} | Px={e['execPrice']} | Fee={e['execFee']}")

# Find closed PnL records around 22:00 - 22:45
print("\nClosed PnL around 22:00 - 22:45:")
for p in pnls:
    t = datetime.fromtimestamp(int(p["updatedTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if ("2026-10-13 22:" in t) and p["symbol"] == "CHIPUSDT":
        print(f"[{t} UTC] OrderId={p['orderId']} | Side={p['side']} | Qty={p['qty']} | EntryPx={p['avgEntryPrice']} | ExitPx={p['avgExitPrice']} | PnL={p['closedPnl']}")

# ----------------------------------------------------
# CASE 2: #16 (PONS LONG around 2026-10-14 07:35:02 UTC)
# Entry 593 PONS, closes total 822 PONS, entry 0.3329 vs exchange avg 0.3240
# ----------------------------------------------------
print("\n" + "="*80)
print("CASE 2: Pos #16 - PONS LONG (2026-10-14 ~07:35 UTC)")
print("="*80)
for o in all_orders:
    t = datetime.fromtimestamp(int(o["createdTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if "2026-10-14 07:" in t or "2026-10-14 08:0" in t:
        if o["symbol"] == "PONSUSDT":
            print(f"[{t} UTC] OrderId={o['orderId']} | LinkId={o.get('orderLinkId')} | Side={o['side']} | Qty={o['qty']} | Status={o['orderStatus']} | Type={o['orderType']} | ReduceOnly={o.get('reduceOnly')} | TrigPx={o.get('triggerPrice')}")

print("\nExecutions around 07:15 - 08:05 for PONSUSDT:")
for e in execs:
    t = datetime.fromtimestamp(int(e["execTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if ("2026-10-14 07:" in t or "2026-10-14 08:0" in t) and e["symbol"] == "PONSUSDT":
        print(f"[{t} UTC] ExecId={e['execId']} | OrderId={e['orderId']} | LinkId={e.get('orderLinkId')} | Side={e['side']} | Qty={e['execQty']} | Px={e['execPrice']} | Fee={e['execFee']}")

print("\nClosed PnL around 07:15 - 08:05 for PONSUSDT:")
for p in pnls:
    t = datetime.fromtimestamp(int(p["updatedTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if ("2026-10-14 07:" in t or "2026-10-14 08:0" in t) and p["symbol"] == "PONSUSDT":
        print(f"[{t} UTC] OrderId={p['orderId']} | Side={p['side']} | Qty={p['qty']} | EntryPx={p['avgEntryPrice']} | ExitPx={p['avgExitPrice']} | PnL={p['closedPnl']}")

# ----------------------------------------------------
# CASE 3: #12 / #14 (CHIP SHORT 04:25:05 and 05:10:05 UTC)
# Shared avg entry 0.05691 but different close times
# ----------------------------------------------------
print("\n" + "="*80)
print("CASE 3: Pos #12 & #14 - CHIP SHORT (2026-10-14 04:25 to 07:05 UTC)")
print("="*80)
for o in all_orders:
    t = datetime.fromtimestamp(int(o["createdTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if any(h in t for h in ["2026-10-14 04:", "2026-10-14 05:", "2026-10-14 06:", "2026-10-14 07:0"]):
        if o["symbol"] == "CHIPUSDT" and ("SHORT" in o.get("orderLinkId", "") or o["side"] in ("Sell", "Buy")):
            print(f"[{t} UTC] OrderId={o['orderId']} | LinkId={o.get('orderLinkId')} | Side={o['side']} | Qty={o['qty']} | Status={o['orderStatus']} | Type={o['orderType']} | ReduceOnly={o.get('reduceOnly')} | TrigPx={o.get('triggerPrice')}")

print("\nClosed PnL around 04:25 - 07:10 for CHIPUSDT:")
for p in pnls:
    t = datetime.fromtimestamp(int(p["updatedTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if any(h in t for h in ["2026-10-14 04:", "2026-10-14 05:", "2026-10-14 06:", "2026-10-14 07:0"]) and p["symbol"] == "CHIPUSDT":
        print(f"[{t} UTC] OrderId={p['orderId']} | Side={p['side']} | Qty={p['qty']} | EntryPx={p['avgEntryPrice']} | ExitPx={p['avgExitPrice']} | PnL={p['closedPnl']}")

# ----------------------------------------------------
# CASE 4: #19 (CHIP SHORT 2026-10-14 08:40:02 UTC)
# Two 1380 CHIP closes; total PnL 2.6443 USDT
# ----------------------------------------------------
print("\n" + "="*80)
print("CASE 4: Pos #19 - CHIP SHORT (2026-10-14 08:40 to 12:05 UTC)")
print("="*80)
for o in all_orders:
    t = datetime.fromtimestamp(int(o["createdTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if any(h in t for h in ["2026-10-14 08:4", "2026-10-14 09:", "2026-10-14 10:", "2026-10-14 11:"]):
        if o["symbol"] == "CHIPUSDT":
            print(f"[{t} UTC] OrderId={o['orderId']} | LinkId={o.get('orderLinkId')} | Side={o['side']} | Qty={o['qty']} | Status={o['orderStatus']} | Type={o['orderType']} | ReduceOnly={o.get('reduceOnly')} | TrigPx={o.get('triggerPrice')}")

print("\nExecutions around 08:40 - 12:05 for CHIPUSDT:")
for e in execs:
    t = datetime.fromtimestamp(int(e["execTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if any(h in t for h in ["2026-10-14 08:4", "2026-10-14 09:", "2026-10-14 10:", "2026-10-14 11:"]) and e["symbol"] == "CHIPUSDT":
        print(f"[{t} UTC] ExecId={e['execId']} | OrderId={e['orderId']} | LinkId={e.get('orderLinkId')} | Side={e['side']} | Qty={e['execQty']} | Px={e['execPrice']} | Fee={e['execFee']}")

print("\nClosed PnL around 08:40 - 12:05 for CHIPUSDT:")
for p in pnls:
    t = datetime.fromtimestamp(int(p["updatedTime"])/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if any(h in t for h in ["2026-10-14 08:4", "2026-10-14 09:", "2026-10-14 10:", "2026-10-14 11:"]) and p["symbol"] == "CHIPUSDT":
        print(f"[{t} UTC] OrderId={p['orderId']} | Side={p['side']} | Qty={p['qty']} | EntryPx={p['avgEntryPrice']} | ExitPx={p['avgExitPrice']} | PnL={p['closedPnl']}")
