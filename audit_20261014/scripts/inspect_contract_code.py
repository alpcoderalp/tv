import ast
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("tv_signal_strategy.py", "r", encoding="utf-8") as f:
    code = f.read()

lines = code.splitlines()

def find_func_lines(func_name):
    for i, line in enumerate(lines):
        if re.match(rf"^\s*(async\s+)?def\s+{func_name}\b", line):
            start = i
            base_indent = len(line) - len(line.lstrip())
            # Find the header end (colon)
            body_start = i + 1
            while body_start < len(lines) and not lines[body_start-1].rstrip().endswith(":"):
                body_start += 1
            for j in range(body_start, len(lines)):
                l = lines[j]
                if l.strip() and (len(l) - len(l.lstrip())) <= base_indent:
                    return start, j
            return start, len(lines)
    return None, None

funcs_to_inspect = [
    "_hybrid_apply_05_be",
    "_try_trigger_hybrid_management",
    "_hybrid_execute_tp1_close",
    "_handle_phase2_trailing",
    "_fee_adjusted_r_targets",
    "_ensure_position_r_geometry",
    "_apply_amount_rules",
    "_round_price",
    "_process_signal"
]

print("=== FUNCTION INSPECTION ===")
for fn in funcs_to_inspect:
    s, e = find_func_lines(fn)
    print(f"Function {fn}: lines {s+1 if s else 'None'} to {e+1 if e else 'None'} ({e-s if s and e else 0} lines)")

# Check BE threshold formula in _hybrid_apply_05_be
s, e = find_func_lines("_hybrid_apply_05_be")
if s and e:
    print("\n--- _hybrid_apply_05_be (first 50 lines) ---")
    for k in range(s, min(s + 50, e)):
        print(f"{k+1}: {lines[k]}")

# Check 1R formula in _fee_adjusted_r_targets
s, e = find_func_lines("_fee_adjusted_r_targets")
if s and e:
    print("\n--- _fee_adjusted_r_targets ---")
    for k in range(s, e):
        print(f"{k+1}: {lines[k]}")

# Check TP1 quantity in _hybrid_execute_tp1_close
s, e = find_func_lines("_hybrid_execute_tp1_close")
if s and e:
    print("\n--- _hybrid_execute_tp1_close (first 40 lines) ---")
    for k in range(s, min(s + 40, e)):
        print(f"{k+1}: {lines[k]}")
