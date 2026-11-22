"""Deployment config tests do not contact Google or a model provider."""
import json
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).parents[1]


def setup(path, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts/setup_docker.py"),
                           "--output", str(path), *args], capture_output=True, text=True)


def test_fixture_config_is_private_and_stable(tmp_path):
    path = tmp_path / ".env"
    first = setup(path)
    assert first.returncode == 0, first.stderr
    values = dotenv_values(path)
    assert values["RETAIL_MODE"] == "fixture"
    assert values["WEBUI_ADMIN_PASSWORD"] not in first.stdout
    assert path.stat().st_mode & 0o777 == 0o600
    original = path.read_bytes()
    assert setup(path).returncode == 0
    assert path.read_bytes() == original


def test_live_credentials_are_imported_without_rotating_local_identity(tmp_path):
    path, credentials = tmp_path / ".env", tmp_path / "provider.env"
    credentials.write_text("GOOGLE_CLOUD_PROJECT=example-project\nGEMINI_API_KEY=private-test-key\n"
                           "GEMINI_MODEL=example-model\nEMBEDDING_PROVIDER=none\n")
    result = setup(path, "--live", "--credentials", str(credentials))
    assert result.returncode == 0, result.stderr
    values = dotenv_values(path)
    assert values["GEMINI_API_KEY"] == "private-test-key"
    assert "private-test-key" not in result.stdout + result.stderr
    assert values["GOOGLE_APPLICATION_CREDENTIALS"] == "/run/secrets/google.json"
    assert "local-token" not in values["API_TOKENS_JSON"]
    assert set(json.loads(values["API_TOKENS_JSON"]).values()) == {"alice", "bob"}
    credentials.write_text(credentials.read_text().replace("private-test-key", "replacement-key"))
    assert setup(path, "--live", "--credentials", str(credentials)).returncode == 0
    updated = dotenv_values(path)
    assert updated["GEMINI_API_KEY"] == "replacement-key"
    assert updated["WEBUI_ADMIN_PASSWORD"] == values["WEBUI_ADMIN_PASSWORD"]
    assert updated["LABEL_SECRET"] == values["LABEL_SECRET"]


def test_invalid_live_settings_are_redacted_and_do_not_write(tmp_path):
    path, credentials = tmp_path / ".env", tmp_path / "provider.env"
    credentials.write_text("GEMINI_API_KEY=do-not-print-me\nMAX_SECONDS=secret-invalid-value\n")
    result = setup(path, "--live", "--credentials", str(credentials))
    assert result.returncode != 0
    assert "do-not-print-me" not in result.stdout + result.stderr
    assert "secret-invalid-value" not in result.stdout + result.stderr
    assert not path.exists()


def test_mode_change_cannot_reuse_fixture_database_identity(tmp_path):
    path = tmp_path / ".env"
    assert setup(path).returncode == 0
    original = path.read_bytes()
    assert setup(path, "--live").returncode != 0
    assert path.read_bytes() == original


def test_google_runtime_copy_is_readable_inside_container_but_private_on_host(tmp_path):
    source = tmp_path / "google.json"
    source.write_text('{"type":"authorized_user","refresh_token":"private-refresh"}')
    source.chmod(0o600)
    credentials = tmp_path / "provider.env"
    credentials.write_text("GOOGLE_CLOUD_PROJECT=p\nGEMINI_API_KEY=test-key\nGEMINI_MODEL=m\nEMBEDDING_PROVIDER=none\n")
    runtime = tmp_path / "private-runtime" / "google.json"
    result = setup(tmp_path / ".env", "--live", "--credentials", str(credentials),
                   "--google-credentials", str(source), "--google-output", str(runtime))
    assert result.returncode == 0, result.stderr
    assert runtime.read_bytes() == source.read_bytes()
    assert runtime.parent.stat().st_mode & 0o777 == 0o700
    assert runtime.stat().st_mode & 0o777 == 0o644
    assert source.stat().st_mode & 0o777 == 0o600
    assert "private-refresh" not in result.stdout + result.stderr
