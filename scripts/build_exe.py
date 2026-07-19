"""Build a standalone Windows executable using PyInstaller."""

import os
import subprocess
import sys
from pathlib import Path


def find_pyinstaller():
    try:
        import PyInstaller
        p = Path(PyInstaller.__file__).parent.parent / 'Scripts' / 'pyinstaller.exe'
        if p.exists():
            return str(p)
    except ImportError:
        pass
    python_dir = Path(sys.executable).parent
    for p in [python_dir / 'Scripts' / 'pyinstaller.exe',
              python_dir.parent / 'Scripts' / 'pyinstaller.exe']:
        if p.exists():
            return str(p)
    return None


def build():
    print("=" * 60)
    print("Reddit Dashboard — Windows Executable Builder")
    print("=" * 60)

    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("✗ PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    repo_root = Path(__file__).parent.parent
    entry_point = repo_root / "main.py"

    if not entry_point.exists():
        print(f"✗ Entry point not found: {entry_point}")
        sys.exit(1)

    pyinstaller_exe = find_pyinstaller()
    base_cmd = [pyinstaller_exe] if pyinstaller_exe else [sys.executable, "-m", "PyInstaller"]

    cmd = base_cmd + [
        "--name=RedditDashboard",
        "--windowed",
        "--onefile",
        "--clean",
        str(entry_point),
    ]

    print(f"\nCommand: {' '.join(cmd)}\n")

    try:
        subprocess.run(cmd, check=True, cwd=str(repo_root))
        exe = repo_root / "dist" / "RedditDashboard.exe"
        size_mb = exe.stat().st_size / (1024 * 1024) if exe.exists() else 0
        print(f"\n✓ Build successful! ({size_mb:.1f} MB)")
        print(f"  Location: {exe}")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build()
