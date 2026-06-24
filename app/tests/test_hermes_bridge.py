from pathlib import Path

from app.services.hermes_bridge import HermesBridge


def test_detect_home_prefers_configured_hermes_home(tmp_path, monkeypatch):
    stale_home = tmp_path / "wsl-home"
    windows_home = tmp_path / "windows-home"
    (stale_home / ".hermes").mkdir(parents=True)
    (windows_home / ".hermes").mkdir(parents=True)
    (windows_home / ".hermes" / "config.yaml").write_text("model:\n  provider: nvidia\n", encoding="utf-8")

    class FakePath:
        @staticmethod
        def home():
            return stale_home

        def __new__(cls, value=""):
            if value == "/mnt/c/Users/Stephane_Arnoux":
                return windows_home
            return Path(value)

    monkeypatch.setattr("app.services.hermes_bridge.Path", FakePath)

    bridge = HermesBridge()

    assert bridge.home == windows_home
    assert bridge.config_path == windows_home / ".hermes" / "config.yaml"
