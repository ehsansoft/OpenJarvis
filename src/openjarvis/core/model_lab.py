"""Bounded synthetic evaluations, never executing generated code or tools."""

import ast
import json
import re
import time

from openjarvis.core.types import Message, Role


def _code_check(text, values, expected):
    code = re.sub(r"^```(?:python)?\s*|\s*```$", "", text.strip())
    tree = ast.parse(code)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return False
    fn = tree.body[0]
    if (
        fn.decorator_list
        or fn.args.defaults
        or len(fn.body) != 1
        or not isinstance(fn.body[0], ast.Return)
    ):
        return False
    names = [a.arg for a in fn.args.args]
    if len(names) != len(values):
        return False
    env = dict(zip(names, values))

    def value(node):
        if isinstance(node, ast.Name) and node.id in env:
            return env[node.id]
        if (
            isinstance(node, ast.Constant)
            and type(node.value) in {int, float}
            and abs(node.value) < 1_000_000
        ):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult)
        ):
            a, b = value(node.left), value(node.right)
            return (
                a + b
                if isinstance(node.op, ast.Add)
                else a - b
                if isinstance(node.op, ast.Sub)
                else a * b
            )
        raise ValueError("Unsupported generated expression")

    return value(fn.body[0].value) == expected


def run_evaluations(engine, models, *, max_cases=4):
    allowed = {"local/fast", "local/code", "local/research"}
    if not models or set(models) - allowed:
        raise ValueError("Select existing local capability aliases")
    cases = [
        (
            "arithmetic",
            "Return only the integer: 19 + 28.",
            lambda s: s.strip() == "47",
        ),
        (
            "structured",
            'Return JSON only: {"status":"ok","count":3}.',
            lambda s: json.loads(s) == {"status": "ok", "count": 3},
        ),
        (
            "bounded-code",
            (
                "Return only a Python function add(a,b) which returns their s"
                "um. No imports, calls or extra statements."
            ),
            lambda s: all(
                _code_check(s, values, expected)
                for values, expected in [([-7, 3], -4), ([0, 0], 0), ([8, 9], 17)]
            ),
        ),
        (
            "grounded-answer",
            (
                "Source [1]: The synthetic project status is paused. What is "
                "its status? Answer in one sentence with [1]."
            ),
            lambda s: "paused" in s.lower() and "[1]" in s,
        ),
    ][:max_cases]
    rows = []
    for model in models:
        for name, prompt, check in cases:
            start = time.monotonic()
            try:
                result = engine.generate(
                    [Message(role=Role.USER, content=prompt)],
                    model=model,
                    max_tokens=192,
                    temperature=0.0,
                )
                content = result.get("content", "")
                passed = bool(check(content))
                routing = result.get("routing", {})
                rows.append(
                    {
                        "alias": model,
                        "case": name,
                        "status": "PASS" if passed else "FAIL",
                        "seconds": round(time.monotonic() - start, 2),
                        "selected_model": routing.get(
                            "selected_model", result.get("model", model)
                        ),
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "alias": model,
                        "case": name,
                        "status": "FAIL",
                        "seconds": round(time.monotonic() - start, 2),
                        "error_type": type(exc).__name__,
                    }
                )
    return {
        "scope": (
            "Small synthetic checks; no generated code or tools executed."
            " Not general model qualification."
        ),
        "results": rows,
        "passed": sum(r["status"] == "PASS" for r in rows),
    }
