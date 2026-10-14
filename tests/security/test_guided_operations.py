"""Personal operations must not inherit outbound or write authority."""

from unittest.mock import MagicMock

from openjarvis.core.config import JarvisConfig
from openjarvis.core.events import EventBus
from openjarvis.security import setup_security
from openjarvis.server.auth_middleware import AuthMiddleware


def test_editor_api_is_authenticated_when_keyed():
    assert AuthMiddleware._requires_auth("/router/v1/models")
    assert AuthMiddleware._requires_auth("/router/v1/chat/completions")


def test_personal_operations_policy_keeps_inventory_and_memory_only(tmp_path):
    cfg = JarvisConfig()
    cfg.security.private_operations = True
    cfg.security.audit_log_path = str(tmp_path / "audit.db")
    sec = setup_security(cfg, MagicMock(), EventBus())
    policy = sec.capability_policy
    assert policy is not None
    for identity in ["orchestrator", "mcp", "dashboard:research", "new-agent"]:
        assert policy.check(identity, "memory:read", "retrieval")
        assert policy.check(identity, "file:read", "drive_inventory")
        assert not policy.check(identity, "network:fetch", "web_search")
        assert not policy.check(identity, "file:write", "apply_patch")
        assert not policy.check(identity, "code:execute", "shell_exec")
