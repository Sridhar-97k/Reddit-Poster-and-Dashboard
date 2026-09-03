"""Build framework for the Reddit Dashboard — produces a standalone Windows .exe.

The build runs inside a dedicated, isolated virtual environment (``.build-venv``)
that contains ONLY this app's declared dependencies plus PyInstaller. That keeps
the result independent of whatever is installed in your active/conda environment,
so the executable is reproducible on any machine and as small as possible (no
stray numpy / PIL / lxml / Qt-WebEngine bloat).

Run this (or double-click ``build.bat``) to build ``dist/RedditDashboard.exe``.

Stages:
    [1/4] Prepare the isolated build environment (.build-venv + deps + PyInstaller)
    [2/4] Generate the app icons (assets/icon.png + icon.ico)
    [3/4] Clean previous build artifacts (build/, dist/, *.spec)
    [4/4] Bundle main.py into a single windowed .exe (icon + required DLLs)

Usage:
    python scripts/build_exe.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = REPO_ROOT / "main.py"
APP_NAME = "RedditDashboard"
ASSETS_DIR = REPO_ROOT / "assets"
ICON_ICO = ASSETS_DIR / "icon.ico"
BUILD_VENV = REPO_ROOT / ".build-venv"

# Heavy packages this app never uses. Excluded so that even a bloated build
# environment cannot leak them into the executable.
EXCLUDES = ["numpy", "PIL", "lxml", "pandas", "matplotlib", "scipy",
            "tkinter", "IPython", "jupyter", "pytest", "PyQt5.QtWebEngineWidgets"]


def _run(cmd):
    """Run a command from the repo root, echoing it first."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))


def _venv_python():
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python"
    return BUILD_VENV / sub / exe


def prepare_build_env():
    print("\n[1/4] Preparing isolated build environment...")
    if not _venv_python().exists():
        print(f"  creating virtual environment: {BUILD_VENV.name}")
        _run([sys.executable, "-m", "venv", str(BUILD_VENV)])
    else:
        print(f"  reusing existing {BUILD_VENV.name}")

    vpy = str(_venv_python())
    _run([vpy, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    req = REPO_ROOT / "requirements.txt"
    if req.exists():
        _run([vpy, "-m", "pip", "install", "-r", str(req), "--quiet"])
    _run([vpy, "-m", "pip", "install", "pyinstaller", "--quiet"])


def generate_icons():
    print("\n[2/4] Generating app icons...")
    _run([str(_venv_python()), str(REPO_ROOT / "scripts" / "make_icons.py")])


def clean():
    print("\n[3/4] Cleaning previous build artifacts...")
    targets = [REPO_ROOT / "build", REPO_ROOT / "dist", REPO_ROOT / f"{APP_NAME}.spec"]
    removed = False
    for path in targets:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            print(f"  removed {path.name}/")
            removed = True
        elif path.exists():
            path.unlink()
            print(f"  removed {path.name}")
            removed = True
    if not removed:
        print("  (nothing to clean)")


def _conda_dll_binaries():
    """Conda's stdlib C-extensions (pyexpat, _lzma, _bz2, _ctypes) depend on DLLs
    in the env's Library\\bin that PyInstaller doesn't auto-bundle — causing
    "DLL load failed while importing pyexpat" at runtime. Bundle any we find.
    No-op on a standard, non-conda Python where these aren't split into DLLs."""
    patterns = ["libexpat*.dll", "liblzma*.dll", "*bz2*.dll", "ffi*.dll", "libffi*.dll"]
    search_dirs = [
        Path(sys.prefix) / "Library" / "bin",
        Path(getattr(sys, "base_prefix", sys.prefix)) / "Library" / "bin",
        Path(sys.prefix) / "DLLs",
    ]
    args, seen = [], set()
    for d in search_dirs:
        if not d.is_dir():
            continue
        for pat in patterns:
            for dll in d.glob(pat):
                if dll.name.lower() not in seen:
                    seen.add(dll.name.lower())
                    args.append(f"--add-binary={dll}{os.pathsep}.")
    return args


def build():
    print("\n[4/4] Building the executable...")
    if not ENTRY_POINT.exists():
        print(f"  [ERROR] Entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    cmd = [str(_venv_python()), "-m", "PyInstaller",
           f"--name={APP_NAME}",
           "--windowed",     # no console window (GUI app)
           "--onefile",      # single self-contained .exe
           "--clean",        # clear PyInstaller's own cache
           "--noconfirm"]    # don't prompt to overwrite
    for mod in EXCLUDES:
        cmd.append(f"--exclude-module={mod}")
    if ICON_ICO.exists():
        cmd.append(f"--icon={ICON_ICO}")
        # Bundle assets so the in-app window icon (icon.png) resolves at runtime
        cmd.append(f"--add-data={ASSETS_DIR}{os.pathsep}assets")

    dll_args = _conda_dll_binaries()
    if dll_args:
        print(f"  bundling {len(dll_args)} DLL(s) needed by pyexpat/_lzma/_bz2/_ctypes")
        cmd += dll_args

    cmd.append(str(ENTRY_POINT))
    _run(cmd)

    exe = REPO_ROOT / "dist" / f"{APP_NAME}.exe"
    size_mb = exe.stat().st_size / (1024 * 1024) if exe.exists() else 0
    print(f"\n[OK] Build complete: {exe}  ({size_mb:.1f} MB)")


def main():
    print("=" * 60)
    print(f"{APP_NAME} - Windows executable build")
    print("=" * 60)
    try:
        prepare_build_env()
        generate_icons()
        clean()
        build()
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
