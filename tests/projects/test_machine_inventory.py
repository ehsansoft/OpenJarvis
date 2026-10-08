"""Tests for developer workstation inventory."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from openjarvis.projects.machine_inventory import (
    ToolInstallation,
    analyze_machine_inventory,
    detect_voicebox,
    detect_wampserver,
)


def test_machine_recommends_path_cleanup_for_multiple_node_installs() -> None:
    tools = [
        ToolInstallation(
            name="node",
            version="v22.0.0",
            executable=r"C:\node\node.exe",
            locations=[r"C:\node\node.exe", r"D:\node\node.exe"],
        ),
        ToolInstallation(
            name="npm",
            version="10.0.0",
            executable=r"C:\node\npm.cmd",
            locations=[r"C:\node\npm.cmd"],
        ),
    ]

    recommendations = analyze_machine_inventory(
        tools,
        {"reachable": False, "shared_digest_groups": []},
        {"reachable": False},
        {"detected": False, "components": []},
    )

    assert any(
        item["kind"] == "multiple-tool-installations"
        for item in recommendations
    )


def test_voicebox_detects_registered_and_loaded_models() -> None:
    def fake_http(url: str, *, timeout: float = 4.0):
        if url.endswith("/health"):
            return {"status": "ok", "backend": "pytorch"}
        if url.endswith("/models/status"):
            return {
                "models": [
                    {
                        "model_name": "kokoro",
                        "display_name": "Kokoro 82M",
                        "engine": "kokoro",
                        "downloaded": True,
                        "loaded": True,
                        "size_mb": 350,
                    },
                    {
                        "model_name": "whisper-base",
                        "display_name": "Whisper Base",
                        "engine": "whisper",
                        "downloaded": True,
                        "loaded": True,
                        "size_mb": 300,
                    },
                    {
                        "model_name": "qwen-0.6b",
                        "display_name": "Qwen3 0.6B",
                        "engine": "llm",
                        "downloaded": True,
                        "loaded": True,
                        "size_mb": 1200,
                    },
                    {
                        "model_name": "tada-3b-ml",
                        "display_name": "TADA 3B Multilingual",
                        "engine": "tada",
                        "downloaded": False,
                        "loaded": False,
                        "size_mb": 8000,
                    },
                ]
            }
        raise AssertionError(url)

    with mock.patch(
        "openjarvis.projects.machine_inventory._http_json",
        side_effect=fake_http,
    ):
        result = detect_voicebox("http://127.0.0.1:17493")

    assert result["reachable"] is True
    assert result["model_count"] == 4
    assert result["downloaded_count"] == 3
    assert result["loaded_count"] == 3
    assert "kokoro" in result["loaded_models"]
    assert "whisper-base" in result["downloaded_models"]


def test_voicebox_unreachable_is_nonfatal() -> None:
    with mock.patch(
        "openjarvis.projects.machine_inventory._http_json",
        side_effect=OSError("connection refused"),
    ):
        result = detect_voicebox("http://127.0.0.1:17493")

    assert result["reachable"] is False
    assert result["models"] == []
    assert "connection refused" in result["error"]


def test_wamp_detection_maps_versions_vhosts_and_wordpress(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wamp64"
    conf = root / "wampmanager.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text(
        'phpVersion = "8.3.1"\n'
        'apacheVersion = "2.4.62"\n'
        'mysqlVersion = "8.0.40"\n',
        encoding="utf-8",
    )

    vhosts = (
        root
        / "bin"
        / "apache"
        / "apache2.4.62"
        / "conf"
        / "extra"
        / "httpd-vhosts.conf"
    )
    vhosts.parent.mkdir(parents=True)
    site = root / "www" / "demo"
    site.mkdir(parents=True)
    (site / "wp-config.php").write_text("<?php", encoding="utf-8")
    vhosts.write_text(
        "<VirtualHost *:80>\n"
        "ServerName demo.local\n"
        f'DocumentRoot "{site}"\n'
        "</VirtualHost>\n",
        encoding="utf-8",
    )

    with (
        mock.patch(
            "openjarvis.projects.machine_inventory._candidate_wamp_roots",
            return_value=[root],
        ),
        mock.patch(
            "openjarvis.projects.machine_inventory._service_state",
            return_value="",
        ),
        mock.patch(
            "openjarvis.projects.machine_inventory._port_open",
            return_value=False,
        ),
        mock.patch(
            "openjarvis.projects.machine_inventory._windows_hosts_entries",
            return_value=[],
        ),
    ):
        result = detect_wampserver()

    assert result["active_versions"]["php"] == "8.3.1"
    assert result["active_versions"]["apache"] == "2.4.62"
    assert result["virtual_hosts"][0]["server_name"] == "demo.local"
    assert str(site) in result["wordpress_sites"]


def test_wamp_detection_finds_runtime_components(tmp_path: Path) -> None:
    root = tmp_path / "wamp64"
    php = root / "bin" / "php" / "php8.3.1" / "php.exe"
    apache = (
        root
        / "bin"
        / "apache"
        / "apache2.4.62"
        / "bin"
        / "httpd.exe"
    )
    php.parent.mkdir(parents=True)
    apache.parent.mkdir(parents=True)
    php.write_bytes(b"")
    apache.write_bytes(b"")

    with (
        mock.patch(
            "openjarvis.projects.machine_inventory._candidate_wamp_roots",
            return_value=[root],
        ),
        mock.patch(
            "openjarvis.projects.machine_inventory._component_version",
            return_value="test-version",
        ),
    ):
        result = detect_wampserver()

    assert result["detected"] is True
    kinds = {item["kind"] for item in result["components"]}
    assert "php" in kinds
    assert "apache" in kinds
