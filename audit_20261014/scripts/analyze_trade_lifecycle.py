import json
import datetime
import hashlib
from decimal import Decimal

with open('audit_20261014/raw_api/order_history_normal.json', 'r', encoding='utf-8') as f:
    orders_norm = json.load(f)
with open('audit_20261014/raw_api/order_history_stop.json', 'r', encoding='utf-8') as f:
    orders_stop = json.load(f)
with open('audit_20261014/raw_api/execution_list_history.json', 'r', encoding='utf-8') as f:
    execs = [x for x in json.load(f) if x.get('execType') == 'Trade']
with open('audit_20261014/raw_api/closed_pnl_history.json', 'r', encoding='utf-8') as f:
    pnls = json.load(f)

from datetime import datetime, timezone

DEPLOY_TS_MS = int(datetime(2026, 10, 13, 11, 35, 47, tzinfo=timezone.utc).timestamp() * 1000)
CUTOFF_TS_MS = int(datetime(2026, 10, 14, 12, 5, 6, tzinfo=timezone.utc).timestamp() * 1000)

all_orders = orders_norm + orders_stop

# Find entry orders after deploy
entries = [o for o in orders_norm if o.get('orderLinkId', '').startswith('B41') and int(o.get('createdTime', 0)) >= DEPLOY_TS_MS and int(o.get('createdTime', 0)) <= CUTOFF_TS_MS]
entries.sort(key=lambda x: int(x.get('createdTime', 0)))

print(f"Deploy post-cutoff entries: {len(entries)}")

def stable_int_order_id(raw) -> int:
    s = str(raw or "")
    if not s: return 0
    digest = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return (int(digest[:16], 16) % (10 ** 12)) or 1

for idx, e in enumerate(entries, 1):
    t_iso = datetime.fromtimestamp(int(e['createdTime'])/1000, timezone.utc).isoformat()
    parent_id = stable_int_order_id(e['orderId'])
    # Find initial stop order
    # Stop link ids: H-S-<parent_id>-BB or similar
    stops = [s for s in orders_stop if str(parent_id) in s.get('orderLinkId', '') or e['orderId'] in s.get('orderLinkId', '')]
    # Find TP orders
    tps = [o for o in orders_norm if str(parent_id) in o.get('orderLinkId', '') and o['orderId'] != e['orderId']]
    
    print(f"\n--- Trade #{idx}: parent_id={parent_id} | {e['symbol']} {e['side']} {e['qty']} @ {e.get('avgPrice')} ({t_iso}) ---")
    print(f"  Entry Order: id={e['orderId']} link={e.get('orderLinkId')} status={e['orderStatus']}")
    for s in stops:
        st_iso = datetime.fromtimestamp(int(s['createdTime'])/1000, timezone.utc).isoformat()
        print(f"  Stop Order: id={s['orderId']} link={s.get('orderLinkId')} qty={s['qty']} trigPx={s.get('triggerPrice')} status={s['orderStatus']} ({st_iso})")
    for tp in tps:
        tp_iso = datetime.fromtimestamp(int(tp['createdTime'])/1000, timezone.utc).isoformat()
        print(f"  TP Order: id={tp['orderId']} link={tp.get('orderLinkId')} qty={tp['qty']} px={tp.get('price')} status={tp['orderStatus']} ({tp_iso})")
