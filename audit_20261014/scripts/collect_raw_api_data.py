import urllib.request
import json
import time
import hmac
import hashlib
import os
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

# Output directory for raw API data
raw_dir = "audit_20261014/raw_api"
os.makedirs(raw_dir, exist_ok=True)

# Read credentials from scratch/check_full_account_state.py or env
# To strictly protect secrets, they are only used in-memory for signing and never logged
with open("scratch/check_full_account_state.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
m_key = re.search(r"key\s*=\s*['\"]([^'\"]+)['\"]", text)
m_sec = re.search(r"sec\s*=\s*['\"]([^'\"]+)['\"]", text)

if not m_key or not m_sec:
    raise RuntimeError("API credentials could not be loaded from secret store.")

API_KEY = m_key.group(1)
API_SECRET = m_sec.group(1)
BASE_URL = "https://api-demo.bybit.com"

# Timestamps:
# Deploy was at 2026-10-13 11:35:47 UTC
# Lookback: start from 2026-10-12 00:00:00 UTC (1791763200000) to capture pre-deploy state
# Cutoff: 2026-10-14 12:05:06 UTC (1791979506000)
START_TIME_MS = int(datetime(2026, 10, 12, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
END_TIME_MS = int(datetime(2026, 10, 14, 12, 5, 6, tzinfo=timezone.utc).timestamp() * 1000)

collection_metadata = {
    "collection_start_utc": datetime.now(timezone.utc).isoformat(),
    "base_url": BASE_URL,
    "start_time_ms": START_TIME_MS,
    "end_time_ms": END_TIME_MS,
    "api_calls": []
}

def bybit_get(endpoint, params=None):
    ts = str(int(time.time() * 1000))
    recv_window = "5000"
    query_parts = []
    if params:
        for k, v in sorted(params.items()):
            if v is not None and v != "":
                query_parts.append(f"{k}={v}")
    query_str = "&".join(query_parts)
    full_path = f"{endpoint}?{query_str}" if query_str else endpoint
    
    param_str = f"{ts}{API_KEY}{recv_window}{query_str}"
    sig = hmac.new(API_SECRET.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256).hexdigest()
    
    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-SIGN": sig,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }
    
    url = f"{BASE_URL}{full_path}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    
    call_meta = {
        "endpoint": endpoint,
        "query": query_str,
        "request_time_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_ms": ts
    }
    
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            call_meta["retCode"] = data.get("retCode")
            call_meta["retMsg"] = data.get("retMsg")
            call_meta["status_code"] = resp.status
            collection_metadata["api_calls"].append(call_meta)
            time.sleep(0.05) # gentle pacing
            return data
    except Exception as e:
        call_meta["error"] = str(e)
        collection_metadata["api_calls"].append(call_meta)
        raise

def paginate_get(endpoint, base_params, list_extractor):
    all_items = []
    cursor = ""
    page = 0
    seen_cursors = set()
    
    while True:
        page += 1
        params = dict(base_params)
        if cursor:
            params["cursor"] = cursor
        
        data = bybit_get(endpoint, params)
        ret_code = data.get("retCode", -1)
        if ret_code != 0:
            print(f"Error {ret_code} in {endpoint}: {data.get('retMsg')}")
            break
            
        res = data.get("result", {})
        items = list_extractor(res)
        all_items.extend(items)
        next_cursor = res.get("nextPageCursor", "")
        
        if not next_cursor or next_cursor in seen_cursors or not items:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if page > 50: # safety breaker
            break
            
    return all_items

print("1. Querying Account & Instruments Info...")
# Instruments Info (Linear)
instruments_data = bybit_get("/v5/market/instruments-info", {"category": "linear"})
with open(os.path.join(raw_dir, "instruments_info_linear.json"), "w", encoding="utf-8") as f:
    json.dump(instruments_data, f, indent=2)

# Wallet Balance
wallet_balance = bybit_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})
with open(os.path.join(raw_dir, "wallet_balance_unified.json"), "w", encoding="utf-8") as f:
    json.dump(wallet_balance, f, indent=2)

# Active Positions Snapshot
pos_active = bybit_get("/v5/position/list", {"category": "linear", "settleCoin": "USDT"})
with open(os.path.join(raw_dir, "active_positions_snapshot.json"), "w", encoding="utf-8") as f:
    json.dump(pos_active, f, indent=2)

# Active Normal Orders Snapshot
orders_active = bybit_get("/v5/order/realtime", {"category": "linear", "settleCoin": "USDT"})
with open(os.path.join(raw_dir, "active_orders_normal_snapshot.json"), "w", encoding="utf-8") as f:
    json.dump(orders_active, f, indent=2)

# Active Stop/Conditional Orders Snapshot
stops_active = bybit_get("/v5/order/realtime", {"category": "linear", "settleCoin": "USDT", "orderFilter": "StopOrder"})
with open(os.path.join(raw_dir, "active_orders_stop_snapshot.json"), "w", encoding="utf-8") as f:
    json.dump(stops_active, f, indent=2)

print("2. Paginating History Endpoints (startTime to endTime)...")
# Closed PnL
closed_pnl_all = paginate_get(
    "/v5/position/closed-pnl",
    {"category": "linear", "startTime": START_TIME_MS, "endTime": END_TIME_MS, "limit": 100},
    lambda res: res.get("list", [])
)
with open(os.path.join(raw_dir, "closed_pnl_history.json"), "w", encoding="utf-8") as f:
    json.dump(closed_pnl_all, f, indent=2)

# Executions (Trade History)
executions_all = paginate_get(
    "/v5/execution/list",
    {"category": "linear", "startTime": START_TIME_MS, "endTime": END_TIME_MS, "limit": 100},
    lambda res: res.get("list", [])
)
with open(os.path.join(raw_dir, "execution_list_history.json"), "w", encoding="utf-8") as f:
    json.dump(executions_all, f, indent=2)

# Order History (Normal Orders)
orders_history_all = paginate_get(
    "/v5/order/history",
    {"category": "linear", "startTime": START_TIME_MS, "endTime": END_TIME_MS, "limit": 100},
    lambda res: res.get("list", [])
)
with open(os.path.join(raw_dir, "order_history_normal.json"), "w", encoding="utf-8") as f:
    json.dump(orders_history_all, f, indent=2)

# Order History (Stop Orders)
stops_history_all = paginate_get(
    "/v5/order/history",
    {"category": "linear", "orderFilter": "StopOrder", "startTime": START_TIME_MS, "endTime": END_TIME_MS, "limit": 100},
    lambda res: res.get("list", [])
)
with open(os.path.join(raw_dir, "order_history_stop.json"), "w", encoding="utf-8") as f:
    json.dump(stops_history_all, f, indent=2)

# Transaction Log (account cashflow)
tx_log_all = paginate_get(
    "/v5/account/transaction-log",
    {"accountType": "UNIFIED", "category": "linear", "startTime": START_TIME_MS, "endTime": END_TIME_MS, "limit": 50},
    lambda res: res.get("list", [])
)
with open(os.path.join(raw_dir, "transaction_log.json"), "w", encoding="utf-8") as f:
    json.dump(tx_log_all, f, indent=2)

collection_metadata["collection_end_utc"] = datetime.now(timezone.utc).isoformat()
collection_metadata["counts"] = {
    "instruments": len(instruments_data.get("result", {}).get("list", [])),
    "active_positions": len(pos_active.get("result", {}).get("list", [])),
    "active_orders_normal": len(orders_active.get("result", {}).get("list", [])),
    "active_orders_stop": len(stops_active.get("result", {}).get("list", [])),
    "closed_pnl_records": len(closed_pnl_all),
    "executions": len(executions_all),
    "order_history_normal": len(orders_history_all),
    "order_history_stop": len(stops_history_all),
    "transaction_logs": len(tx_log_all)
}

with open(os.path.join(raw_dir, "collection_metadata.json"), "w", encoding="utf-8") as f:
    json.dump(collection_metadata, f, indent=2)

print("\nData Collection Summary:")
for k, v in collection_metadata["counts"].items():
    print(f" - {k}: {v}")
