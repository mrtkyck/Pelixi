@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller --noconsole --onefile --name MyNotes --add-data "static;static" desktop_main.py

echo.
echo Build tamamlandi.
echo Cikti: dist\MyNotes.exe
echo Veri tabani: %%LOCALAPPDATA%%\MyNotes\data\my_notes.db
echo.
pause

endlocal
