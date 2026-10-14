with open("tv_signal_strategy.py", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if "_fee_adjusted_r_levels" in line:
            print(f"{i+1}: {line.strip()[:100]}")
