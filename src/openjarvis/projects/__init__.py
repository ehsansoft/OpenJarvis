"""Local project discovery and registry primitives."""

from openjarvis.projects.discovery import (
    ProjectRecord,
    discover_projects,
    load_registry,
    write_registry,
)

from openjarvis.projects.inventory import (
    DriveInventory,
    analyze_inventory,
    scan_drive_inventory,
    write_inventory,
)


__all__ = [
    "ProjectRecord",
    "discover_projects",
    "load_registry",
    "write_registry",
    "DriveInventory",
    "analyze_inventory",
    "scan_drive_inventory",
    "write_inventory",
]
