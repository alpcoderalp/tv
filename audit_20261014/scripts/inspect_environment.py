import subprocess
import json
import os
import sys
import hashlib
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

os.makedirs("audit_20261014/raw_api", exist_ok=True)
os.makedirs("audit_20261014/scripts", exist_ok=True)
os.makedirs("audit_20261014/evidence", exist_ok=True)

def run_local(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
    return p.stdout.strip(), p.stderr.strip()

def run_ssh(remote_cmd):
    p = subprocess.run(
        ["ssh", "-p", "22022", "-o", "StrictHostKeyChecking=no", "ubuntu@57.129.5.114", remote_cmd],
        capture_output=True, text=True, encoding="utf-8"
    )
    return p.stdout.strip(), p.stderr.strip()

# Local Git info
local_commit, _ = run_local("git rev-parse HEAD")
local_status, _ = run_local("git status --porcelain")
local_branch, _ = run_local("git branch --show-current")

# Local Strategy hash
with open("tv_signal_strategy.py", "rb") as f:
    local_strat_sha = hashlib.sha256(f.read()).hexdigest().upper()

# VPS container state
vps_state_json, _ = run_ssh("docker inspect hummingbot --format '{{json .State}}'")
vps_image_id, _ = run_ssh("docker inspect hummingbot --format '{{.Image}}'")
vps_created, _ = run_ssh("docker inspect hummingbot --format '{{.Created}}'")
vps_strat_sha, _ = run_ssh("docker exec hummingbot sha256sum /home/hummingbot/scripts/tv_signal_strategy.py")
vps_uptime, _ = run_ssh("uptime")
vps_env, _ = run_ssh("docker exec hummingbot env")

# Mask secrets in env
sanitized_env = []
for line in vps_env.splitlines():
    if any(s in line.upper() for s in ["KEY", "SECRET", "PASSWORD", "PASS", "AUTH", "TOKEN"]):
        k = line.split("=")[0]
        sanitized_env.append(f"{k}=[REDACTED]")
    else:
        sanitized_env.append(line)

env_info = {
    "audit_reference_time_utc": "2026-10-14T12:05:06Z",
    "deploy_start_time_utc": "2026-10-13T11:35:47Z",
    "local_git": {
        "commit": local_commit,
        "branch": local_branch,
        "dirty_status": local_status
    },
    "local_strategy_sha256": local_strat_sha,
    "vps_container": {
        "image_id": vps_image_id,
        "created": vps_created,
        "state": json.loads(vps_state_json) if vps_state_json else {},
        "running_strategy_sha256": vps_strat_sha.split()[0].upper() if vps_strat_sha else None,
        "sanitized_env": sanitized_env,
        "host_uptime": vps_uptime
    }
}

with open("audit_20261014/evidence/environment_snapshot.json", "w", encoding="utf-8") as f:
    json.dump(env_info, f, indent=2)

print("Environment snapshot collected:")
print(" - Local Git Commit:", local_commit)
print(" - Local Strategy SHA256:", local_strat_sha)
print(" - VPS Container Strategy SHA256:", env_info["vps_container"]["running_strategy_sha256"])
print(" - VPS Container StartedAt:", env_info["vps_container"]["state"].get("StartedAt"))
print(" - VPS Image ID:", vps_image_id)
