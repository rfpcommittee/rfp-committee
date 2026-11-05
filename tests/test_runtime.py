"""Settings (.env / environment), COMET on and off, and the Windows start-up scripts."""
import os
import shutil
import subprocess
import sys

import pytest

import evaluator as ev
from conftest import ROOT

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="the helper scripts are Windows batch files")


# ---- USE_MODEL and .env
@pytest.mark.parametrize("value,expected", [("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
                                            ("false", False), ("0", False), ("", False), ("maybe", False)])
def test_use_model_flag(monkeypatch, value, expected):
    monkeypatch.setenv("USE_MODEL", value) if value else monkeypatch.delenv("USE_MODEL", raising=False)
    monkeypatch.setattr(ev, "BASE_DIR", os.path.join(ROOT, "tests"))        # a folder without a .env
    assert ev.use_model() is expected


def test_use_model_reads_env_file_and_environment_wins(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("# comment\nUSE_MODEL=true  # on\nCOMET_BATCH_SIZE=8\n", encoding="utf-8")
    monkeypatch.setattr(ev, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("USE_MODEL", raising=False)
    monkeypatch.delenv("COMET_BATCH_SIZE", raising=False)
    assert ev.use_model() is True and ev.setting("COMET_BATCH_SIZE") == "8"
    monkeypatch.setenv("USE_MODEL", "false")
    assert ev.use_model() is False


def test_no_env_file_means_comet_off(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("USE_MODEL", raising=False)
    assert ev.use_model() is False


# ---- missing COMET library / model
def test_missing_comet_library_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "comet", None)           # makes "from comet import ..." fail
    with pytest.raises(ev.ModelUnavailable, match="unbabel-comet"):
        ev.load_comet_model()


def test_comet_available_reflects_the_installed_package(monkeypatch):
    def missing(_):
        raise ev.md.PackageNotFoundError
    monkeypatch.setattr(ev.md, "version", missing)
    assert ev.comet_available() is False


def test_unloadable_checkpoint_is_reported(monkeypatch, tmp_path):
    pytest.importorskip("comet")
    bad = tmp_path / "missing.ckpt"
    monkeypatch.setenv("COMET_CHECKPOINT", str(bad))
    with pytest.raises(ev.ModelUnavailable, match="Could not load the COMET model"):
        ev.load_comet_model()


# ---- Windows scripts
def run_bat(tmp_path, name, path_dirs, extra_files=()):
    """Runs a copy of a batch file in an empty folder with a restricted PATH. Returns (exit code, output)."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    shutil.copy(os.path.join(ROOT, name), work / name)
    for f in extra_files:
        shutil.copy(os.path.join(ROOT, f), work / f)
    system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    env = {"PATH": os.pathsep.join(list(path_dirs) + [system32]), "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
           "COMSPEC": os.environ.get("COMSPEC", os.path.join(system32, "cmd.exe")), "TEMP": str(tmp_path)}
    r = subprocess.run([env["COMSPEC"], "/c", name, "nopause"], cwd=work, env=env, capture_output=True, text=True,
                       timeout=600)
    return r.returncode, r.stdout + r.stderr


def fake_bin(tmp_path, cmd, body="@exit /b 1"):
    d = tmp_path / "fakebin"
    d.mkdir(exist_ok=True)
    (d / f"{cmd}.bat").write_text("@echo off\n" + body + "\n")
    return str(d)


@windows_only
def test_run_app_without_a_python_environment_stops_with_a_clear_message(tmp_path):
    code, out = run_bat(tmp_path, "run_app.bat", [])
    assert code == 1 and "setup_model_env.bat first" in out


def _base_python_lacks_libraries():
    exe = os.path.join(sys.base_prefix, "python.exe")
    return os.path.exists(exe) and subprocess.run([exe, "-c", "import streamlit, pandas, sacrebleu"],
                                                  capture_output=True).returncode != 0


@windows_only
@pytest.mark.skipif(not _base_python_lacks_libraries(), reason="no Python without the libraries to try")
def test_run_app_when_the_libraries_are_missing(tmp_path):
    code, out = run_bat(tmp_path, "run_app.bat", [sys.base_prefix])      # a real python.exe that cannot import them
    assert code == 1 and "setup_model_env.bat first" in out
    assert "Traceback" not in out


@windows_only
def test_setup_stops_when_python_312_is_missing(tmp_path):
    code, out = run_bat(tmp_path, "setup_model_env.bat", [], ["requirements.txt"])     # no py launcher on the PATH
    assert code == 1 and "Python 3.12 was not found" in out
    assert "Setup finished" not in out


@windows_only
@pytest.mark.skipif(subprocess.run(["py", "-3.12", "--version"], capture_output=True).returncode != 0
                    if sys.platform == "win32" else True, reason="Python 3.12 is not installed")
def test_setup_fails_fast_when_an_install_fails(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "requirements.txt").write_text("no-such-package-for-this-test==0.0.0\n")
    code, out = run_bat(tmp_path, "setup_model_env.bat", [os.path.dirname(shutil.which("py"))], [])
    assert code == 1
    assert "ERROR:" in out and "Setup finished" not in out


def test_scripts_report_errors_with_exit_code_1():
    for name in ("setup_model_env.bat", "run_app.bat"):
        text = open(os.path.join(ROOT, name), encoding="utf-8").read()
        assert "exit /b 1" in text and "errorlevel" in text
