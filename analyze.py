#!/usr/bin/env python3
"""Turn results.csv into the tables, slopes and prediction needed for REPORT.md.

  python analyze.py            # prints markdown, writes loglog.png if matplotlib exists
"""

import csv
import math
import sys


def load(path="results.csv"):
    with open(path, newline="") as fh:
        return [dict(op=r["op"], n=int(r["n"]), m=int(r["m"]), match=float(r["match"]),
                     counter=int(r["counter"]), seconds=float(r["seconds"]),
                     out=int(r["out_tuples"])) for r in csv.DictReader(fh)]


def slope(xs, ys):
    """Least-squares slope of log10(y) against log10(x)."""
    lx, ly = [math.log10(x) for x in xs], [math.log10(y) for y in ys]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def human(secs):
    if secs < 120:
        return f"{secs:.1f} s"
    if secs < 7200:
        return f"{secs / 60:.1f} min"
    if secs < 172800:
        return f"{secs / 3600:.1f} hours"
    return f"{secs / 86400:.1f} days"


def main():
    rows = load(sys.argv[1] if len(sys.argv) > 1 else "results.csv")
    base = {op: sorted([r for r in rows if r["op"] == op and r["match"] == 1.0 and r["n"] == r["m"]],
                       key=lambda r: r["n"]) for op in ("join", "select", "project")}

    print("## Join table (match rate 1)\n")
    print("| n | m | comparisons | n*m | wall time (s) | output tuples |")
    print("|---|---|---|---|---|---|")
    for r in base["join"]:
        print(f"| {r['n']} | {r['m']} | {r['counter']} | {r['n'] * r['m']} | {r['seconds']:.3f} | {r['out']} |")
    bad = [r for r in base["join"] if r["counter"] != r["n"] * r["m"]]
    print(f"\ncomparisons == n*m for every row: {'yes' if not bad else 'NO, check ' + str([r['n'] for r in bad])}\n")

    print("## Select and project (match rate 1)\n")
    print("| n | select counter | select time (s) | project counter | project time (s) |")
    print("|---|---|---|---|---|")
    sel = {r["n"]: r for r in base["select"]}
    pro = {r["n"]: r for r in base["project"]}
    for n in sorted(set(sel) & set(pro)):
        print(f"| {n} | {sel[n]['counter']} | {sel[n]['seconds']:.4f} | {pro[n]['counter']} | {pro[n]['seconds']:.4f} |")

    print("\n## Log-log slopes (log10 time vs log10 n)\n")
    slopes = {}
    for op, rs in base.items():
        rs = [r for r in rs if r["seconds"] > 0]
        if len(rs) >= 2:
            slopes[op] = slope([r["n"] for r in rs], [r["seconds"] for r in rs])
            print(f"- {op}: slope = {slopes[op]:.3f}")

    if base["join"]:
        last = base["join"][-1]
        per = last["seconds"] / last["counter"]
        print("\n## Prediction for n = m = 1,000,000\n")
        print(f"Comparisons = n*m = 1,000,000 * 1,000,000 = 1e12")
        print(f"Seconds per comparison measured at n={last['n']}: {last['seconds']:.3f} / {last['counter']} = {per:.3e}")
        est = per * 1e12
        print(f"Prediction A: 1e12 * {per:.3e} = {est:.3e} s = {human(est)}")
        if "join" in slopes:
            est2 = last["seconds"] * (1e6 / last["n"]) ** slopes["join"]
            print(f"Prediction B (slope): {last['seconds']:.3f} * (1e6/{last['n']})^{slopes['join']:.3f} = {est2:.3e} s = {human(est2)}")

    study = sorted([r for r in rows if r["op"] == "join" and r["n"] == r["m"] and r["match"] != 1.0
                    or (r["op"] == "join" and r["match"] == 1.0 and r["n"] == r["m"] and
                        any(x["match"] != 1.0 and x["n"] == r["n"] for x in rows))],
                   key=lambda r: (r["n"], r["match"]))
    if study:
        print("\n## Match-rate study\n")
        print("| n | match rate | comparisons | wall time (s) | output tuples |")
        print("|---|---|---|---|---|")
        for r in study:
            print(f"| {r['n']} | {r['match']:g} | {r['counter']} | {r['seconds']:.3f} | {r['out']} |")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure()
        for op, rs in base.items():
            if rs:
                plt.loglog([r["n"] for r in rs], [max(r["seconds"], 1e-6) for r in rs], marker="o", label=op)
        plt.xlabel("n (tuples per relation)")
        plt.ylabel("wall time (s)")
        plt.legend()
        plt.grid(True, which="both", alpha=0.3)
        plt.savefig("loglog.png", dpi=150)
        print("\nwrote loglog.png")
    except ImportError:
        print("\n(matplotlib not installed: pip install matplotlib to get loglog.png)")


if __name__ == "__main__":
    main()
