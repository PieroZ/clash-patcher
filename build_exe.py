r"""Budowanie pliku .exe z clash_exe_config.py przy pomocy PyInstaller.

Uruchomienie (wiersz polecen Windows, w katalogu clash-patcher):

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt -r requirements-build.txt
    python build_exe.py

Wynik: dist\clash-exe-config.exe - jeden plik, bez okna konsoli, nie wymaga
zainstalowanego Pythona ani PySide6.

Ten sam skrypt uruchamia GitHub Actions (.github/workflows/build-exe.yml).
Komunikaty sa bez polskich znakow, zeby nie psuly sie w konsoli Windows.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRY = HERE / "clash_exe_config.py"
DEFAULT_NAME = "clash-exe-config"
EXE_SUFFIX = ".exe" if os.name == "nt" else ""

# Program uzywa tylko QtCore / QtGui / QtWidgets. Reszta Qt (przegladarka,
# multimedia, 3D, QML) to kilkaset MB, ktore nigdy sie nie wczytaja.
EXCLUDED_MODULES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "tkinter",
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Buduje plik .exe z clash_exe_config.py (PyInstaller).",
    )
    p.add_argument(
        "--name", default=DEFAULT_NAME, metavar="NAZWA",
        help="nazwa pliku wynikowego bez rozszerzenia (domyslnie: %(default)s)",
    )
    p.add_argument(
        "--icon", metavar="PLIK.ICO",
        help="ikona pliku .exe (opcjonalnie, repozytorium nie zawiera ikony)",
    )
    p.add_argument(
        "--onedir", action="store_true",
        help="katalog z plikami zamiast jednego .exe (szybszy start programu)",
    )
    p.add_argument(
        "--console", action="store_true",
        help="zostaw okno konsoli - przydatne do diagnostyki bledow",
    )
    p.add_argument(
        "--dist", default=str(HERE / "dist"), metavar="KATALOG",
        help="gdzie zapisac wynik (domyslnie: dist)",
    )
    return p.parse_args(argv)


def require(module, req_file):
    """Konczy prace z czytelnym komunikatem, jesli brakuje zaleznosci."""
    try:
        __import__(module)
    except ImportError:
        sys.exit(
            f"Brak modulu {module}.\n"
            f'Zainstaluj zaleznosci:  "{sys.executable}" -m pip install -r {req_file}'
        )


def remove(path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main(argv=None):
    args = parse_args(argv)

    if not ENTRY.exists():
        sys.exit(f"Nie znaleziono {ENTRY}")
    if os.name != "nt":
        print(
            "Uwaga: PyInstaller nie buduje plikow .exe dla Windows na innym systemie - "
            "wynikiem bedzie program dla biezacego systemu.",
            file=sys.stderr,
        )

    require("PySide6", "requirements.txt")
    require("PyInstaller", "requirements-build.txt")

    dist_dir = Path(args.dist).resolve()
    work_dir = HERE / "build"
    result_path = dist_dir / (args.name if args.onedir else args.name + EXE_SUFFIX)

    # Usuwamy poprzedni wynik, zeby nie zostal po nieudanej budowie.
    for stale in (dist_dir / args.name, dist_dir / (args.name + EXE_SUFFIX), work_dir / args.name):
        remove(stale)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", args.name,
        "--onedir" if args.onedir else "--onefile",
        "--console" if args.console else "--windowed",
        "--distpath", str(dist_dir),
        "--workpath", str(work_dir),
        "--specpath", str(work_dir),
        # clash_exe_config.py importuje clash_exe_patches z tego katalogu.
        "--paths", str(HERE),
    ]
    for module in EXCLUDED_MODULES:
        cmd += ["--exclude-module", module]
    if args.icon:
        icon = Path(args.icon).resolve()
        if not icon.exists():
            sys.exit(f"Nie znaleziono ikony {icon}")
        cmd += ["--icon", str(icon)]
    cmd.append(str(ENTRY))

    mode = "katalog" if args.onedir else "jeden plik"
    console = "z konsola" if args.console else "bez konsoli"
    print(f"Buduje {result_path.name} ({mode}, {console}) - to potrwa chwile...", flush=True)
    code = subprocess.run(cmd, cwd=str(HERE)).returncode
    if code != 0:
        print("\nBudowanie nie udalo sie - komunikat PyInstallera jest powyzej.", file=sys.stderr)
        return code

    if not result_path.exists():
        print(f"\nPyInstaller zakonczyl sie bez bledu, ale nie ma {result_path}", file=sys.stderr)
        return 1

    if result_path.is_dir():
        size = sum(f.stat().st_size for f in result_path.rglob("*") if f.is_file())
    else:
        size = result_path.stat().st_size
    print(f"\nGotowe: {result_path} ({size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
