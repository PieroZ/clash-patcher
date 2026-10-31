@echo off
rem Clash Patcher - uruchamianie dwuklikiem.
rem Mozna tez przeciagnac plik CLASH.EXE / clash95.exe na ten plik.
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
    echo Nie znaleziono Pythona.
    echo Zainstaluj go z https://www.python.org/downloads/ i zaznacz "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Pierwsze uruchomienie: tworze srodowisko Pythona...
    %PY% -m venv venv || goto :error
)
"venv\Scripts\python.exe" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo Instaluje PySide6, to potrwa chwile...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

"venv\Scripts\python.exe" clash_exe_config.py %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Cos poszlo nie tak - skopiuj komunikat powyzej i wyslij go autorowi.
pause
exit /b 1
