@echo off
setlocal

set "APP_ROOT=%~dp0"
if "%APP_ROOT:~-1%"=="\" set "APP_ROOT=%APP_ROOT:~0,-1%"

set "PORT=8011"
set "URL=http://127.0.0.1:%PORT%/"

cd /d "%APP_ROOT%"

start "Pelixi Sunucu" /min cmd /k "\"%APP_ROOT%\Pelixi-Serve.cmd\""
timeout /t 3 /nobreak >nul

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "%URL%"
) else if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" "%URL%"
) else (
  start "" "%URL%"
)

endlocal
