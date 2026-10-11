"""Bounded inventory questions and factual formatting without model guesses."""

from __future__ import annotations

import json

_QUESTIONS = {
    "/system",
    "what do you got information about my system",
    "what do you know about my system",
    "what do you know about my computer",
    "show my system information",
    "show my workstation summary",
}


def is_machine_summary_question(text: str) -> bool:
    return " ".join(text.casefold().strip().rstrip("?.!").split()) in _QUESTIONS


def format_machine_summary(content: str) -> str:
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Machine summary must be an object")
    memory = data.get("total_memory_bytes")
    ram = (
        f"{memory / 2**30:.1f} GiB RAM"
        if isinstance(memory, (int, float))
        else "RAM not recorded"
    )
    gpus = ", ".join(str(x) for x in data.get("gpus", []) if x) or "not recorded"
    return (
        "Your cached workstation inventory records "
        f"{data.get('platform', 'an unknown OS')} "
        f"{data.get('platform_release', '')}, {ram}, and GPU: {gpus}.\n\n"
        f"It lists {data.get('ollama_models', 'an unknown number of')} Ollama models "
        f"and {data.get('tools_detected', 'an unknown number of')} developer tools. "
        f"WampServer detected: {data.get('wampserver_detected', 'unknown')}. "
        "Voicebox reachable at scan time: "
        f"{data.get('voicebox_reachable', 'unknown')}.\n\n"
        f"Inventory captured: {data.get('generated_at', 'unknown')}. "
        "This is saved inventory; current service availability may have changed. "
        "Refresh it with `jarvis projects machine-scan`."
    )
