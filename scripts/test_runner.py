#!/usr/bin/env python3
"""
Test runner script for Home Assistant custom components.
Manages a dedicated testing virtual environment, installs the specified Home Assistant version,
and runs pytest or launches a live local instance.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

# Workspace Root
ROOT_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT_DIR / ".venv_ha_test"
CONFIG_DIR = ROOT_DIR / "config_ha_test"

# OS-specific executable paths for local venv
if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
    VENV_PYTEST = VENV_DIR / "Scripts" / "pytest.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_PIP = VENV_DIR / "bin" / "pip"
    VENV_PYTEST = VENV_DIR / "bin" / "pytest"


def get_required_python(ha_version: str) -> float:
    """Determine the minimum Python version required by the specified HA version (2026.5+ requires 3.14)."""
    return 3.14


def setup_venv(ha_version: str, force_clean: bool = False):
    """Set up the local virtual environment and install dependencies."""
    venv_needs_recreate = False
    print(f"\n[Test Runner] Verifying virtual environment in: {VENV_DIR}")
    if VENV_PYTHON.exists():
        try:
            res = subprocess.run(
                [str(VENV_PYTHON), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                check=True
            )
            venv_version = res.stdout.strip()
            host_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            if venv_version != host_version:
                print(f"[Test Runner] Virtual env Python ({venv_version}) does not match host Python ({host_version}). Recreating...")
                venv_needs_recreate = True
            else:
                print(f"[Test Runner] Virtual env exists and uses Python {venv_version} (matches host).")
        except Exception:
            print("[Test Runner] Virtual env is corrupted or unusable. Recreating...")
            venv_needs_recreate = True
    else:
        print("[Test Runner] Virtual env does not exist yet.")

    if force_clean or venv_needs_recreate:
        if VENV_DIR.exists():
            print(f"[Test Runner] Removing old virtual environment: {VENV_DIR}")
            shutil.rmtree(VENV_DIR)

    if not VENV_DIR.exists():
        print(f"[Test Runner] Creating a new virtual environment: {VENV_DIR}")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    print("[Test Runner] Upgrading pip to the latest version...")
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=True)

    print(f"[Test Runner] Installing/Updating requirements for Home Assistant {ha_version}...")
    ha_pkg = "homeassistant" if ha_version.lower() == "latest" else f"homeassistant=={ha_version}"
    
    requirements = [
        ha_pkg,
        "pytest>=8.0.0",
        "pytest-homeassistant-custom-component",
        "pyserial-asyncio-fast>=0.11",
        "pyserial>=3.5",
        "rf-protocols",
    ]
    print(f"[Test Runner] Pip requirements to install: {', '.join(requirements)}")
    subprocess.run([str(VENV_PIP), "install"] + requirements, check=True)
    print("[Test Runner] All dependencies are successfully installed and up to date.")


def run_tests(pytest_args: list):
    """Run pytest suite in the local virtualenv."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR) + (";" if os.name == "nt" else ":") + env.get("PYTHONPATH", "")
    
    # Setup cross-platform serial_asyncio mapping, Windows stubs, and silence logging noise
    inner_cmd = (
        "import sys, unittest.mock, logging, atexit; "
        "logging.root.setLevel(logging.WARNING); "
        "logging.Logger.setLevel = lambda self, level: None; "
        "logging.basicConfig = lambda *a, **k: None; "
        "atexit.register(lambda: logging.disable(logging.CRITICAL)); "
        "sys.modules['serial_asyncio'] = __import__('serial_asyncio_fast'); "
    )
    if os.name == "nt":
        inner_cmd += (
            "sys.modules['fcntl'] = unittest.mock.MagicMock(); "
            "sys.modules['resource'] = unittest.mock.MagicMock(); "
            "exec('try:\\n    import pytest_socket\\n    pytest_socket.disable_socket = lambda *a, **k: None\\nexcept ImportError:\\n    pass'); "
        )
    inner_cmd += (
        "import pytest; "
        "ret = pytest.main(sys.argv[1:]); "
        "import logging; "
        "logging.disable(logging.CRITICAL); "
        "sys.exit(ret)"
    )

    # Automatically force-enable sockets on Windows
    extended_args = pytest_args.copy()
    if os.name == "nt" and "--force-enable-socket" not in " ".join(extended_args):
        extended_args.append("--force-enable-socket")

    # Set default asyncio-mode to auto to avoid pytest 9 warnings/errors
    if "--asyncio-mode" not in " ".join(extended_args):
        extended_args.extend(["--asyncio-mode", "auto"])

    # Always run in verbose mode to show tests in progress
    if "-v" not in extended_args and "--verbose" not in extended_args:
        extended_args.append("-v")

    # Silence PytestAssertRewriteWarning about pytest_socket
    if "-W" not in " ".join(extended_args):
        extended_args.extend(["-W", "ignore::pytest.PytestAssertRewriteWarning"])

    cmd = [str(VENV_PYTHON), "-c", inner_cmd] + extended_args
        
    print(f"\n[Test Runner] Running pytest with arguments: {extended_args}")
    print("[Test Runner] -------------------------------------------------------------")
    result = subprocess.run(cmd, env=env, cwd=str(ROOT_DIR))
    print("[Test Runner] -------------------------------------------------------------")
    print(f"[Test Runner] Tests finished with exit code: {result.returncode}")
    sys.exit(result.returncode)


def start_live_ha(port: int):
    """Start a live local Home Assistant instance."""
    prepare_config_dir(port)
    print(f"Starting Home Assistant UI on http://localhost:{port}...")
    
    # Setup cross-platform serial_asyncio mapping and Windows stubs
    inner_cmd = (
        "import sys, runpy, unittest.mock, asyncio; "
        "sys.modules['serial_asyncio'] = __import__('serial_asyncio_fast'); "
        "sys.modules['pymicro_vad'] = unittest.mock.MagicMock(); "
        "sys.modules['pyspeex_noise'] = unittest.mock.MagicMock(); "
        "sys.modules['webrtc_noise_gain'] = unittest.mock.MagicMock(); "
        "asyncio.events.AbstractEventLoop.add_signal_handler = lambda *a, **k: None; "
    )
    if os.name == "nt":
        inner_cmd += (
            "import signal; "
            "signal.SIGHUP = 1; "
            "sys.modules['fcntl'] = unittest.mock.MagicMock(); "
            "sys.modules['resource'] = unittest.mock.MagicMock(); "
            "asyncio.ProactorEventLoop.add_signal_handler = lambda *a, **k: None; "
        )
    inner_cmd += "sys.argv[0] = 'homeassistant'; runpy.run_module('homeassistant', run_name='__main__')"
    
    cmd = [
        str(VENV_PYTHON),
        "-c",
        inner_cmd,
        "--config", str(CONFIG_DIR),
        "--ignore-os-check"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nHome Assistant stopped by user.")


def prepare_config_dir(port: int):
    """Create configuration directory and copy integration files."""
    CONFIG_DIR.mkdir(exist_ok=True)
    target_cc_dir = CONFIG_DIR / "custom_components"
    target_cc_dir.mkdir(exist_ok=True)
    
    target_integration_dir = target_cc_dir / "rflink_ui"
    if target_integration_dir.exists():
        shutil.rmtree(target_integration_dir)
        
    shutil.copytree(ROOT_DIR / "custom_components" / "rflink_ui", target_integration_dir)
    print(f"Copied integration to: {target_integration_dir}")

    config_yaml = CONFIG_DIR / "configuration.yaml"
    with open(config_yaml, "w", encoding="utf-8") as f:
        f.write("# Home Assistant Testing Configuration\n")
        f.write("default_config:\n")
        f.write("http:\n")
        f.write(f"  server_port: {port}\n")
        f.write("logger:\n")
        f.write("  default: info\n")
        f.write("  logs:\n")
        f.write("    custom_components.rflink_ui: debug\n")
    print(f"Configured configuration.yaml with server_port={port}")

    # Bypass onboarding steps (except user creation which requires complex security hashes)
    storage_dir = CONFIG_DIR / ".storage"
    storage_dir.mkdir(exist_ok=True)
    onboarding_file = storage_dir / "onboarding"
    with open(onboarding_file, "w", encoding="utf-8") as f:
        f.write(
            '{\n'
            '  "version": 4,\n'
            '  "minor_version": 1,\n'
            '  "key": "onboarding",\n'
            '  "data": {\n'
            '    "done": [\n'
            '      "core_config",\n'
            '      "integration",\n'
            '      "analytics"\n'
            '    ]\n'
            '  }\n'
            '}\n'
        )
    print("Bypassed onboarding steps (core_config, integration, analytics).")


def main():
    parser = argparse.ArgumentParser(description="Home Assistant Custom Component Test & Run Script")
    parser.add_argument(
        "-v", "--version",
        default="2026.5.0",
        help="Home Assistant version to install/use (default: 2026.5.0, or specify 'latest')"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run a live local Home Assistant UI instance instead of running tests"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run automated tests (default action)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8123,
        help="Port to run Home Assistant UI on (default: 8123)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Force re-creation of the testing virtual environment"
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed directly to pytest (must be preceded by '--')"
    )

    args = parser.parse_args()

    pytest_args = args.pytest_args
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
        
    if not pytest_args:
        pytest_args = ["tests"]

    if args.version.lower() != "latest":
        try:
            parts = [int(p) for p in args.version.split(".")]
            while len(parts) < 3:
                parts.append(0)
            if parts < [2026, 5, 0]:
                print(f"Error: Home Assistant version {args.version} is not supported.")
                print("The minimum supported Home Assistant version for this integration is 2026.5.0.")
                sys.exit(1)
        except ValueError:
            print("Error: Invalid version format. Use YYYY.MM.patch or 'latest'.")
            sys.exit(1)

    # Check local Python version vs HA requirements
    host_py_ver = sys.version_info
    req_py_ver = get_required_python(args.version)
    host_ver_float = host_py_ver.major + (host_py_ver.minor / 100)
    
    print(f"[Test Runner] Host Environment: Python {host_py_ver.major}.{host_py_ver.minor}.{host_py_ver.micro} ({os.name.upper()})")
    
    if host_ver_float < req_py_ver:
        print(f"Error: Current Python {host_py_ver.major}.{host_py_ver.minor} is too old for Home Assistant {args.version}.")
        print(f"Home Assistant {args.version} requires Python {req_py_ver} or newer.")
        print(f"Please run this script using Python {req_py_ver} or newer.")
        sys.exit(1)

    print(f"[Test Runner] Target HA Version: {args.version} (requires Python {req_py_ver}+)")
    setup_venv(args.version, force_clean=args.clean)
    if args.run:
        start_live_ha(args.port)
    else:
        run_tests(pytest_args)


if __name__ == "__main__":
    main()
