"""Local project discovery and registry primitives."""

from openjarvis.projects.discovery import (
    ProjectRecord,
    discover_projects,
    load_registry,
    write_registry,
)

__all__ = [
    "ProjectRecord",
    "discover_projects",
    "load_registry",
    "write_registry",
]
