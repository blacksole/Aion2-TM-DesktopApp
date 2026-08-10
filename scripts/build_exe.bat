@echo off
cd /d "%~dp0.."
echo Baue Aion2 TM (Onedir)...
call .venv\Scripts\activate.bat
pyinstaller "Aion2 TM.spec" --clean --noconfirm
echo.
echo Build abgeschlossen: dist\Aion2 TM\
pause
