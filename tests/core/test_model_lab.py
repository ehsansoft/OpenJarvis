from unittest.mock import MagicMock

import pytest

from openjarvis.core.model_lab import _code_check, run_evaluations


def test_generated_code_is_parsed_without_execution():
    assert _code_check("def add(a,b):\n return a+b", [-7, 3], -4)
    with pytest.raises(ValueError):
        _code_check(
            'def add(a,b):\n return __import__("os").system("anything")', [-7, 3], -4
        )


def test_evaluation_report_does_not_store_outputs_or_use_remote_alias():
    engine = MagicMock()
    engine.generate.return_value = {
        "content": "47",
        "routing": {"selected_model": "qwen3.5:2b"},
    }
    result = run_evaluations(engine, ["local/fast"], max_cases=1)
    assert result["passed"] == 1
    assert "content" not in result["results"][0]
    with pytest.raises(ValueError):
        run_evaluations(engine, ["free/research"])
