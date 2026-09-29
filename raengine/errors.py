"""Every user-facing error in the engine is a RAError.

kind is one of: Lexical, Syntax, Name, Schema, Type, Data.
pos is a 0-based character offset into the query text (None for data-file errors).
"""


class RAError(Exception):
    def __init__(self, kind, message, pos=None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.pos = pos


def format_error(err, source=None):
    """Render an error as a message plus (when possible) the query line and a caret."""
    head = f"{err.kind} error"
    if err.pos is not None and source is not None:
        pos = min(err.pos, len(source))
        line_start = source.rfind("\n", 0, pos) + 1
        line_end = source.find("\n", pos)
        if line_end == -1:
            line_end = len(source)
        line_no = source.count("\n", 0, pos) + 1
        col = pos - line_start
        return (
            f"{head} at position {pos} (line {line_no}, column {col + 1}): {err.message}\n"
            f"  {source[line_start:line_end]}\n"
            f"  {' ' * col}^"
        )
    return f"{head}: {err.message}"
