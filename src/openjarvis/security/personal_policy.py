"""An explicit local read-only baseline; public inference remains separate."""

from openjarvis.security.capabilities import CapabilityPolicy


def private_operations_policy():
    policy = CapabilityPolicy(default_deny=True)
    for name in (
        "drive_inventory",
        "machine_inventory",
        "project_registry",
        "hygiene_report",
        "voicebox_status",
        "git_status",
        "git_diff",
    ):
        policy.grant("_default", "file:read", name)
    for name in ("retrieval", "memory_search", "memory_retrieve"):
        policy.grant("_default", "memory:read", name)
    return policy
