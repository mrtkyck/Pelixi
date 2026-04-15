@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller --noconsole --onedir --name MyNotes --add-data "static;static" desktop_main.py

if exist "dist\KULLANIM.txt" copy /Y "dist\KULLANIM.txt" "dist\MyNotes\KULLANIM.txt" >nul

echo.
echo Klasorlu build tamamlandi.
echo Cikti klasoru: dist\MyNotes
echo Ana dosya: dist\MyNotes\MyNotes.exe
echo Veri tabani: %%LOCALAPPDATA%%\MyNotes\data\my_notes.db
echo.
pause

endlocal
