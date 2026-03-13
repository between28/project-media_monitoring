@echo off
setlocal

cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
  echo PyInstaller is not installed.
  echo Run this first:
  echo     python -m pip install pyinstaller
  exit /b 1
)

pyinstaller --noconfirm --clean packaging\MediaMonitor.spec
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo.
echo Build completed:
echo     dist\MediaMonitor\MediaMonitor.exe
