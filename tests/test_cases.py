import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raengine import RAError, parse, render_tree, run_query, load_relations, format_error
from raengine.tokenizer import tokenize
from raengine.nodes import cond_str

EMPLOYEES = """
// employees and their departments
Employees (EID, Name, Age, DID) = {
  E1, John, 32, D1
  E2, Alice, 28, D2
  E3, Bob, 29, D1
}
"""

EMP_DEPT = """
Emp (EID, Name, DID, MgrID) = {
  1, Ann, 10, 0
  2, Bo, 10, 1
  3, Cy, 20, 1
}
Dept (DID, DName) = {
  10, Sales
  20, Eng
}
"""


def run(query, data):
    rel, _ = run_query(query, load_relations(data))
    return rel


def texts(src):
    return [t.text for t in tokenize(src)][:-1]


def err(query, data=""):
    with_db = load_relations(data)
    try:
        run_query(query, with_db)
    except RAError as e:
        return e
    raise AssertionError("expected an RAError")


def single_col(name, *vals):
    return f"{name} (x) = {{\n" + "".join(f"  {v}\n" for v in vals) + "}\n"


class Tokenizer(unittest.TestCase):
    def test_01_no_whitespace(self):
        self.assertEqual(texts("select[x1=3](R)"), ["select", "[", "x1", "=", "3", "]", "(", "R", ")"])
        parse("select[x1=3](R)")

    def test_02_whitespace_same_tree(self):
        self.assertEqual(render_tree(parse("select[x1=3](R)")), render_tree(parse("select[ x1 = 3 ](R)")))

    def test_03_ge_is_one_token(self):
        self.assertEqual(texts("select[Age>=30](R)"), ["select", "[", "Age", ">=", "30", "]", "(", "R", ")"])

    def test_04_gt_then_negative_number(self):
        toks = tokenize("select[Age>-30](R)")
        self.assertEqual([t.text for t in toks][:6], ["select", "[", "Age", ">", "-30", "]"])
        self.assertEqual(toks[4].type, "NUM")
        self.assertEqual(toks[4].value, -30)

    def test_05_paren_inside_string(self):
        r = run("select[Name='Bob)'](R)", "R (Name, k) = {\n 'Bob)', 1\n Alice, 2\n}")
        self.assertEqual(r.rows, [("Bob)", 1)])

    def test_06_comma_inside_string(self):
        r = run("select[Name='a,b'](R)", "R (Name, k) = {\n 'a,b', 1\n c, 2\n}")
        self.assertEqual(r.rows, [("a,b", 1)])

    def test_07_doubled_quote(self):
        toks = tokenize("select[Name='O''Brien'](R)")
        self.assertEqual(toks[4].value, "O'Brien")
        r = run("select[Name='O''Brien'](R)", "R (Name, k) = {\n 'O''Brien', 1\n Bob, 2\n}")
        self.assertEqual(r.rows, [("O'Brien", 1)])

    def test_08_keyword_as_attribute(self):
        r = run("select[union=3](R)", "R (union, x) = {\n 3, 1\n 4, 2\n}")
        self.assertEqual(r.rows, [(3, 1)])
        r = run("select[not=3 and and=1](R)", "R (not, and) = {\n 3, 1\n 3, 2\n}")
        self.assertEqual(r.rows, [(3, 1)])

    def test_09_unterminated_string(self):
        e = err("select[Name='Bob](R)", "R (Name) = {\n Bob\n}")
        self.assertEqual(e.kind, "Lexical")
        self.assertEqual(e.pos, len("select[Name="))
        self.assertIn("unterminated", e.message)


class GrammarPrecedence(unittest.TestCase):
    def test_10_union_minus_left_grouping(self):
        lines = render_tree(parse("A union B minus C")).split("\n")
        self.assertEqual(lines[0], "Minus")
        self.assertEqual(lines[1], "├── Union")

    def test_11_minus_left_associative_and_data_differs(self):
        lines = render_tree(parse("A minus B minus C")).split("\n")
        self.assertEqual(lines[:2], ["Minus", "├── Minus"])
        data = single_col("A", 1) + single_col("B", 1) + single_col("C", 1)
        self.assertEqual(run("A minus B minus C", data).rows, [])        # (A-B)-C
        self.assertEqual(run("A minus (B minus C)", data).rows, [(1,)])  # A-(B-C)

    def test_12_not_and_or(self):
        c = parse("select[not (a=1 and b=2) or c>3](R)").cond
        self.assertEqual(cond_str(c), "Or(Not(And(Eq(Attr(a), Num(1)), Eq(Attr(b), Num(2)))), Gt(Attr(c), Num(3)))")

    def test_13_and_binds_tighter_than_or(self):
        c = parse("select[a=1 and b=2 or c=3](R)").cond
        self.assertEqual(cond_str(c), "Or(And(Eq(Attr(a), Num(1)), Eq(Attr(b), Num(2))), Eq(Attr(c), Num(3)))")

    def test_14_nested_selects(self):
        r = run("project[Name](select[Age>30](select[DID='D1'](Employees)))", EMPLOYEES)
        self.assertEqual(r.rows, [("John",)])

    def test_15_parentheses_override(self):
        data = single_col("A", 1, 2) + single_col("B", 3) + single_col("C", 2, 3, 9) + single_col("D", 3, 2)
        self.assertEqual(run("(A union B) minus (C intersect D)", data).rows, [(1,)])
        d2 = single_col("A", 1) + single_col("B", 1) + single_col("C", 1)
        self.assertEqual(run("A union B minus C", d2).rows, [])          # default: (A u B) - C
        self.assertEqual(run("A union (B minus C)", d2).rows, [(1,)])    # parens override

    def test_16_missing_paren(self):
        q = "select[Age>30](R"
        e = err(q, "R (Age) = {\n 1\n}")
        self.assertEqual(e.kind, "Syntax")
        self.assertEqual(e.pos, len(q))
        self.assertIn("')'", e.message)

    def test_17_empty_project_list(self):
        e = err("project[](R)", "R (a) = {\n 1\n}")
        self.assertEqual(e.kind, "Syntax")
        self.assertEqual(e.pos, len("project["))


class Semantics(unittest.TestCase):
    def test_18_compare_two_columns(self):
        r = run("select[A=B](R)", "R (A, B) = {\n 1, 1\n 1, 2\n 3, 3\n}")
        self.assertEqual(sorted(r.rows), [(1, 1), (3, 3)])

    def test_19_qualified_join(self):
        r = run("Emp join[Emp.DID=Dept.DID] Dept", EMP_DEPT)
        self.assertEqual(r.display_names(), ["Emp.EID", "Emp.Name", "Emp.DID", "Emp.MgrID", "Dept.DID", "Dept.DName"])
        self.assertEqual(len(r.rows), 3)
        self.assertIn((1, "Ann", 10, 0, 10, "Sales"), r.rows)

    def test_20_self_join_needs_rename(self):
        r = run("rename[E2](Emp) join[Emp.MgrID=E2.EID] Emp", EMP_DEPT)
        self.assertEqual(len(r.rows), 2)
        self.assertIn((1, "Ann", 10, 0, 2, "Bo", 10, 1), r.rows)
        e = err("Emp join[Emp.MgrID=Emp.EID] Emp", EMP_DEPT)
        self.assertEqual(e.kind, "Schema")

    def test_21_union_incompatible(self):
        e = err("R union S", "R (x, y) = {\n 1, 2\n}\nS (x) = {\n 1\n}")
        self.assertEqual(e.kind, "Schema")
        e = err("R union S", "R (x) = {\n 1\n}\nS (y) = {\n 1\n}")
        self.assertEqual(e.kind, "Schema")

    def test_22_number_vs_string(self):
        e = err("select[Age>'30'](Employees)", EMPLOYEES)
        self.assertEqual(e.kind, "Type")

    def test_23_project_dedupes(self):
        self.assertEqual(len(run("project[DID](Employees)", EMPLOYEES).rows), 2)

    def test_24_project_repeated_attribute_is_error(self):
        e = err("project[Name, Name](Employees)", EMPLOYEES)
        self.assertEqual(e.kind, "Schema")

    def test_25_empty_result_prints_cleanly(self):
        out = run("select[Age>100](Employees)", EMPLOYEES).format()
        self.assertIn("EID", out)
        self.assertIn("(0 tuples)", out)


class Extras(unittest.TestCase):
    def test_duplicates_collapse_on_load(self):
        self.assertEqual(len(load_relations(single_col("R", 1, 1, 2))["R"].rows), 2)

    def test_quoted_number_is_string(self):
        e = err("select[x>3](R)", "R (x) = {\n '30'\n}")
        self.assertEqual(e.kind, "Type")

    def test_unknown_relation_and_attribute(self):
        self.assertEqual(err("Nope", EMPLOYEES).kind, "Name")
        self.assertEqual(err("select[Salary>1](Employees)", EMPLOYEES).kind, "Name")

    def test_ambiguous_attribute_after_times(self):
        e = err("Emp times Dept join[DID=1] Emp", EMP_DEPT)
        self.assertIn(e.kind, ("Name", "Schema"))
        self.assertEqual(err("select[DID=10](Emp times Dept)", EMP_DEPT).kind, "Name")

    def test_missing_operand_and_unmatched_paren(self):
        self.assertEqual(err("A union", single_col("A", 1)).kind, "Syntax")
        e = err("A)", single_col("A", 1))
        self.assertEqual(e.kind, "Syntax")
        self.assertEqual(e.pos, 1)

    def test_intersect_binds_tighter_than_union(self):
        lines = render_tree(parse("A union B intersect C")).split("\n")
        self.assertEqual(lines[0], "Union")

    def test_counters(self):
        db = load_relations(EMP_DEPT + EMPLOYEES)
        _, s = run_query("Emp join[Emp.DID=Dept.DID] Dept", db)
        self.assertEqual(s.join_comparisons, 3 * 2)
        _, s = run_query("select[Age>1](Employees)", db)
        self.assertEqual(s.select_evals, 3)

    def test_error_formatting_has_caret_and_no_traceback(self):
        q = "select[Age>30](R"
        try:
            parse(q)
        except RAError as e:
            text = format_error(e, q)
            self.assertIn("Syntax error at position 16", text)
            self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()
