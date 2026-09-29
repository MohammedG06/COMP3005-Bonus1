#!/usr/bin/env python3
"""Data generator for the performance study: R(a, b) and S(b, c).

  python gen.py --n 1000 --m 1000 --match 1 --out data/gen.ra

a is unique in R and c is unique in S, so neither relation has duplicate tuples.
b values are drawn uniformly from a domain of size round(m / match), so each R tuple
joins with about `match` S tuples on average (output size is about n * match).
"""

import argparse
import random


def generate(n, m, match=1.0, seed=0):
    rng = random.Random(seed)
    domain = max(1, round(m / match))
    r_rows = [(i, rng.randrange(domain)) for i in range(n)]
    s_rows = [(rng.randrange(domain), i) for i in range(m)]
    return r_rows, s_rows, domain


def write_file(path, r_rows, s_rows):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("R (a, b) = {\n")
        for a, b in r_rows:
            fh.write(f"  {a}, {b}\n")
        fh.write("}\n\nS (b, c) = {\n")
        for b, c in s_rows:
            fh.write(f"  {b}, {c}\n")
        fh.write("}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True, help="tuples in R")
    ap.add_argument("--m", type=int, required=True, help="tuples in S")
    ap.add_argument("--match", type=float, default=1.0, help="avg S tuples matching each R tuple")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    r, s, dom = generate(a.n, a.m, a.match, a.seed)
    write_file(a.out, r, s)
    print(f"wrote {a.out}: |R|={len(r)} |S|={len(s)} domain of b={dom}")
