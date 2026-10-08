"""Configuration tests for the personal control-plane additions."""

from __future__ import annotations

from pathlib import Path

from openjarvis.core.config import JarvisConfig, load_config, validate_config_key


def test_control_plane_nested_config_loads(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[engine.nararouter]\n'
        'host = "https://nara.example/v1"\n\n'
        '[projects]\n'
        'root = "D:\\\\Projects"\n'
        'inventory_root = "D:\\\\"\n'
        'machine_inventory_path = "D:\\\\State\\\\machine.json"\n'
        'cleanup_report_path = "D:\\\\State\\\\cleanup.json"\n'
        'duplicate_report_path = "D:\\\\State\\\\duplicates.json"\n'
        'inventory_max_files = 123456\n'
        'duplicate_min_size_mb = 4\n'
        'cleanup_min_age_days = 45\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert isinstance(config, JarvisConfig)
    assert config.engine.nararouter.host == "https://nara.example/v1"
    assert config.projects.root == r"D:\Projects"
    assert config.projects.inventory_root == "D:\\"
    assert config.projects.inventory_max_files == 123456
    assert config.projects.machine_inventory_path == r"D:\State\machine.json"
    assert config.projects.cleanup_report_path == r"D:\State\cleanup.json"
    assert config.projects.duplicate_report_path == r"D:\State\duplicates.json"
    assert config.projects.duplicate_min_size_mb == 4
    assert config.projects.cleanup_min_age_days == 45


def test_control_plane_config_keys_are_settable() -> None:
    assert validate_config_key("engine.nararouter.host") is str
    assert validate_config_key("projects.root") is str
    assert validate_config_key("projects.inventory_path") is str
    assert validate_config_key("projects.inventory_max_files") is int
    assert validate_config_key("projects.machine_inventory_path") is str
    assert validate_config_key("projects.cleanup_report_path") is str
    assert validate_config_key("projects.duplicate_report_path") is str
    assert validate_config_key("projects.duplicate_min_size_mb") is int
    assert validate_config_key("projects.cleanup_min_age_days") is int
