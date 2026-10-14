import json
import datetime

with open('audit_20261014/raw_api/order_history_normal.json', 'r', encoding='utf-8') as f:
    orders_norm = json.load(f)
with open('audit_20261014/raw_api/order_history_stop.json', 'r', encoding='utf-8') as f:
    orders_stop = json.load(f)
with open('audit_20261014/raw_api/execution_list_history.json', 'r', encoding='utf-8') as f:
    execs = [x for x in json.load(f) if x.get('execType') == 'Trade']
with open('audit_20261014/raw_api/closed_pnl_history.json', 'r', encoding='utf-8') as f:
    pnls = json.load(f)

entries = [o for o in orders_norm if o.get('orderLinkId', '').startswith('B41') and o.get('orderStatus') == 'Filled']
entries.sort(key=lambda x: int(x.get('createdTime', 0)))
print(f"Total Entry Orders: {len(entries)}")
for idx, e in enumerate(entries, 1):
    t = datetime.datetime.fromtimestamp(int(e['createdTime'])/1000, datetime.timezone.utc).isoformat()
    # find execution for entry
    entry_exec = next((x for x in execs if x['orderId'] == e['orderId']), None)
    px = entry_exec['execPrice'] if entry_exec else e.get('avgPrice', '')
    print(f"#{idx}: {t} | {e['symbol']} | {e['side']} | Qty={e['qty']} | Px={px} | LinkId={e['orderLinkId']} | OrderId={e['orderId']}")
