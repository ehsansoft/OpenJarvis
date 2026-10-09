"""Fail-closed routing for personal conversations and private project context."""

from openjarvis.intelligence.free_pool import FreePoolEngine, _is_zero_api_local_engine


class PrivatePoolEngine(FreePoolEngine):
    """Local aliases and local concrete models only; remote failover is impossible."""

    engine_id = "private-pool"

    def __init__(self, engines):
        super().__init__(
            [
                (key, engine)
                for key, engine in engines
                if _is_zero_api_local_engine(key, engine)
            ],
            allow_remote=False,
        )

    def _choices(self, model):
        if model.startswith("free/"):
            model = "local/" + model.split("/", 1)[1]
        return super()._choices(model)


def personal_engine(config, engine, engine_key):
    """Apply the opt-in personal profile's local policy before tools see context."""
    if (
        not config.intelligence.private_routing
        or config.intelligence.allow_private_remote
    ):
        return engine
    from openjarvis.security.guardrails import GuardrailsEngine
    from openjarvis.telemetry.instrumented_engine import InstrumentedEngine

    current = engine
    while isinstance(current, (GuardrailsEngine, InstrumentedEngine)):
        current = (
            current._engine if isinstance(current, GuardrailsEngine) else current._inner
        )
    if isinstance(current, PrivatePoolEngine):
        return engine
    from openjarvis.engine.ollama import OllamaEngine

    local = OllamaEngine(
        host=config.engine.ollama.host or None,
        num_ctx=config.engine.ollama.num_ctx or None,
    )
    entries = [("ollama", local)]
    if engine_key != "ollama" and _is_zero_api_local_engine(engine_key, engine):
        entries.append((engine_key, engine))
    return PrivatePoolEngine(entries)
