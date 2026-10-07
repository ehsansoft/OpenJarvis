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
        'inventory_max_files = 123456\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert isinstance(config, JarvisConfig)
    assert config.engine.nararouter.host == "https://nara.example/v1"
    assert config.projects.root == r"D:\Projects"
    assert config.projects.inventory_root == "D:\\"
    assert config.projects.inventory_max_files == 123456


def test_control_plane_config_keys_are_settable() -> None:
    assert validate_config_key("engine.nararouter.host") is str
    assert validate_config_key("projects.root") is str
    assert validate_config_key("projects.inventory_path") is str
    assert validate_config_key("projects.inventory_max_files") is int
