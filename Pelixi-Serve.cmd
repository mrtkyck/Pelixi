@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "MYNOTES_APP_DIR=%LOCALAPPDATA%\Pelixi"
set "MYNOTES_PORT=8011"

if exist "C:\Program Files\Python313\python.exe" (
  set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
) else (
  set "PYTHON_EXE=python"
)

cd /d "%APP_ROOT%"
title Pelixi Sunucu - 8011
echo Pelixi baslatiliyor...
echo.
echo Veri klasoru: %MYNOTES_APP_DIR%
echo Adres: http://127.0.0.1:%MYNOTES_PORT%/
echo Bu pencereyi kapatirsan Pelixi durur.
echo.
"%PYTHON_EXE%" run.py

endlocal
