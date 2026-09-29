#!/usr/bin/env python3
"""Relational algebra engine CLI.

  python ra.py --tree "project[Name](select[Age>30](Employees))"
  python ra.py --db data/employees.ra "project[DID](Employees)"
  python ra.py --db data/employees.ra --stats "Employees join[Employees.DID=Departments.DID] Departments"
"""

import argparse
import sys
import time
import traceback

from raengine import RAError, format_error, parse, render_tree, evaluate, Stats, load_relations


def main(argv=None):
    ap = argparse.ArgumentParser(description="Relational algebra engine")
    ap.add_argument("query", nargs="?", help="the query text")
    ap.add_argument("-f", "--file", help="read the query from a file instead")
    ap.add_argument("--db", action="append", default=[], help="relation definition file (repeatable)")
    ap.add_argument("--tree", action="store_true", help="print the parse tree and do not execute")
    ap.add_argument("--stats", action="store_true", help="print operator counters and wall time")
    ap.add_argument("--limit", type=int, default=100, help="max tuples to print (default 100)")
    ap.add_argument("--debug", action="store_true", help="show a stack trace on internal errors")
    args = ap.parse_args(argv)

    source = None
    try:
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                source = fh.read()
        elif args.query is not None:
            source = args.query
        else:
            ap.error("give a query, or use -f FILE")

        tree = parse(source)
        if args.tree:
            print(render_tree(tree))
            return 0

        db = {}
        for path in args.db:
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as e:
                raise RAError("Data", f"cannot read {path}: {e.strerror}")
            db.update(load_relations(text, path))

        stats = Stats()
        t0 = time.perf_counter()
        rel = evaluate(tree, db, stats)
        elapsed = time.perf_counter() - t0
        print(rel.format(limit=args.limit))
        if args.stats:
            print(f"[stats] {stats} time={elapsed:.6f}s")
        return 0
    except RAError as e:
        print(format_error(e, source if e.pos is not None else None), file=sys.stderr)
        return 1
    except Exception as e:  # never show a stack trace to the user
        if args.debug:
            traceback.print_exc()
        print(f"Internal error: {type(e).__name__}: {e} (this is a bug; rerun with --debug)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
