from .errors import RAError, format_error
from .parser import parse
from .nodes import render_tree
from .operators import evaluate, Stats
from .relation import load_relations, relation_from_rows, Relation


def run_query(source, db):
    """Parse and evaluate a query. Returns (relation, stats). Raises RAError."""
    tree = parse(source)
    stats = Stats()
    return evaluate(tree, db, stats), stats
