@echo off
setlocal

cd /d "%~dp0"

set "MYNOTES_HOST=0.0.0.0"
set "MYNOTES_PORT=8000"
set "MYNOTES_LOCAL_URL=http://127.0.0.1:8000/"
set "MYNOTES_REMOTE_URL="

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.16.*' -or $_.IPAddress -like '172.17.*' -or $_.IPAddress -like '172.18.*' -or $_.IPAddress -like '172.19.*' -or $_.IPAddress -like '172.2?.*' -or $_.IPAddress -like '172.30.*' -or $_.IPAddress -like '172.31.*' } | Select-Object -First 1 -ExpandProperty IPAddress)"`) do set "MYNOTES_LAN_IP=%%I"

if defined MYNOTES_LAN_IP (
  set "MYNOTES_REMOTE_URL=http://%MYNOTES_LAN_IP%:8000/"
) else (
  set "MYNOTES_REMOTE_URL=IP bulunamadi"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; " ^
  "if ($pids) { $pids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }; " ^
  "$env:MYNOTES_HOST='0.0.0.0'; $env:MYNOTES_PORT='8000'; " ^
  "Start-Process python -ArgumentList 'run.py' -WorkingDirectory '%cd%' -WindowStyle Hidden; " ^
  "Start-Sleep -Seconds 4; " ^
  "if (Test-Path 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe') { Start-Process -FilePath 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' -ArgumentList '%MYNOTES_LOCAL_URL%' } " ^
  "elseif (Test-Path 'C:\Program Files\Microsoft\Edge\Application\msedge.exe') { Start-Process -FilePath 'C:\Program Files\Microsoft\Edge\Application\msedge.exe' -ArgumentList '%MYNOTES_LOCAL_URL%' } " ^
  "elseif (Test-Path 'C:\Program Files\Google\Chrome\Application\chrome.exe') { Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '%MYNOTES_LOCAL_URL%' } " ^
  "else { Start-Process '%MYNOTES_LOCAL_URL%' }"

echo.
echo MyNotes yerel ag modunda baslatildi.
echo Bu bilgisayarda acilacak adres: http://127.0.0.1:8000/
echo Diger bilgisayarlar icin adres: %MYNOTES_REMOTE_URL%
echo.
pause

endlocal
