#!/usr/bin/env python3
"""Run the performance study and append results to results.csv (resumable).

  python benchmark.py                      # all seven sizes, match rate 1
  python benchmark.py --sizes 1000,2000    # quick smoke test
  python benchmark.py --match-study 4000   # comparison-count vs match-rate at one size

The 64000-tuple join is 4.1 billion comparisons; it takes a long time in Python.
Results are written after every run, and finished runs are skipped on restart.
"""

import argparse
import csv
import os
import time

from gen import generate
from raengine import parse, evaluate, Stats, relation_from_rows

FIELDS = ["op", "n", "m", "match", "counter", "seconds", "out_tuples"]
DEFAULT_SIZES = [1000, 2000, 4000, 8000, 16000, 32000, 64000]


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                done.add((row["op"], int(row["n"]), int(row["m"]), float(row["match"])))
    return done


def record(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def run_one(op, n, m, match, path, done):
    if (op, n, m, float(match)) in done:
        print(f"skip {op} n={n} m={m} match={match} (already in {path})")
        return
    r_rows, s_rows, domain = generate(n, m, match)
    db = {"R": relation_from_rows("R", ["a", "b"], r_rows),
          "S": relation_from_rows("S", ["b", "c"], s_rows)}
    query = {"join": "R join[R.b=S.b] S",
             "select": f"select[b<{max(1, domain // 2)}](R)",
             "project": "project[b](R)"}[op]
    tree = parse(query)
    stats = Stats()
    t0 = time.perf_counter()
    rel = evaluate(tree, db, stats)
    secs = time.perf_counter() - t0
    counter = {"join": stats.join_comparisons, "select": stats.select_evals,
               "project": stats.project_tuples}[op]
    row = {"op": op, "n": n, "m": m, "match": match, "counter": counter,
           "seconds": f"{secs:.6f}", "out_tuples": len(rel.rows)}
    record(path, row)
    print(f"{op:8s} n={n:6d} m={m:6d} match={match} counter={counter} time={secs:.3f}s out={len(rel.rows)}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(map(str, DEFAULT_SIZES)))
    ap.add_argument("--match", type=float, default=1.0)
    ap.add_argument("--match-study", type=int, default=0, metavar="N",
                    help="run the join at size N for match rates 1,2,4,8,16")
    ap.add_argument("--out", default="results.csv")
    a = ap.parse_args()
    done = load_done(a.out)
    if a.match_study:
        for mt in (1, 2, 4, 8, 16):
            run_one("join", a.match_study, a.match_study, mt, a.out, done)
    else:
        sizes = [int(x) for x in a.sizes.split(",")]
        for n in sizes:  # cheap operators first, then the expensive join
            run_one("select", n, n, a.match, a.out, done)
            run_one("project", n, n, a.match, a.out, done)
        for n in sizes:
            run_one("join", n, n, a.match, a.out, done)
