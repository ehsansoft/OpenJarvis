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


from openjarvis.projects.machine_inventory import (
    MachineInventory,
    detect_ollama,
    detect_package_caches,
    detect_runtime_managers,
    detect_toolchain,
    detect_wampserver,
    scan_machine_inventory,
    write_machine_inventory,
)
from openjarvis.projects.hygiene import (
    CleanupReport,
    DuplicateReport,
    scan_cleanup_candidates,
    scan_duplicate_files,
    write_cleanup_report,
    write_duplicate_report,
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
    "MachineInventory",
    "detect_ollama",
    "detect_package_caches",
    "detect_runtime_managers",
    "detect_toolchain",
    "detect_wampserver",
    "scan_machine_inventory",
    "write_machine_inventory",
    "CleanupReport",
    "DuplicateReport",
    "scan_cleanup_candidates",
    "scan_duplicate_files",
    "write_cleanup_report",
    "write_duplicate_report",
]
