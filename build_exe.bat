@echo off
rem ======================================================================
rem  Robot Supurge Ajani - Windows EXE derleme betigi
rem
rem  Kullanim (proje klasorunde):
rem      build_exe.bat           tek dosyalik EXE   -> dist\RobotSupurge.exe
rem      build_exe.bat onedir    tek klasorluk EXE  -> dist\RobotSupurge\RobotSupurge.exe
rem
rem  PyInstaller, projeye ozel ".venv-build" sanal ortamina kurulur; global
rem  Python kurulumuna dokunulmaz. build\, dist\, .venv-build\ ve *.spec
rem  dosyalari .gitignore kapsamindadir; derleme ciktisi repoya girmez.
rem ======================================================================
setlocal
cd /d "%~dp0"

set "VENV=.venv-build"
set "PYI_VERSION=6.22.3"

if not exist "%VENV%\Scripts\python.exe" (
    echo [1/4] Sanal ortam olusturuluyor: %VENV%
    python -m venv "%VENV%" || goto :error
)

echo [2/4] PyInstaller %PYI_VERSION% kuruluyor
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet "pyinstaller==%PYI_VERSION%" || goto :error

echo [3/4] Kaynak kod dogrulamasi (--self-test)
"%VENV%\Scripts\python.exe" main.py --self-test || goto :error

set "MODE=--onefile"
if /I "%~1"=="onedir" set "MODE=--onedir"

echo [4/4] EXE derleniyor (%MODE% --windowed)
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean %MODE% --windowed --name RobotSupurge main.py || goto :error

echo.
set "EXE=dist\RobotSupurge.exe"
if /I "%~1"=="onedir" set "EXE=dist\RobotSupurge\RobotSupurge.exe"
echo Tamamlandi: %EXE%
echo EXE dogrulamasi:  start /wait %EXE% --self-test --report self_test_report.txt
exit /b 0

:error
echo.
echo HATA: Derleme basarisiz oldu (hata kodu %errorlevel%).
exit /b 1
