@echo off
REM Registers a Windows Task Scheduler entry that runs check_for_updates.py
REM every Wednesday at 09:00 (User-Wunsch, 2026-08-27: "automatisch auf
REM Abruf jede Woche Mittwoch einmal auf Updates pruefen"). Run this .bat
REM ONCE by hand to install the scheduled task -- it does not need Claude
REM Code or this repo's terminal open afterward, Windows runs it on its own.
REM
REM Safe to re-run: /F overwrites the existing task definition instead of
REM erroring if you run this again (e.g. after moving the repo).
REM
REM To remove it later:
REM     schtasks /delete /tn "Aion2TM_WeeklyDataCheck" /f

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=python

schtasks /create /tn "Aion2TM_WeeklyDataCheck" ^
    /tr "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%check_for_updates.py\"" ^
    /sc weekly /d WED /st 09:00 /f

echo.
echo Done. Check it with:  schtasks /query /tn "Aion2TM_WeeklyDataCheck" /v /fo list
echo Log after each run:   %SCRIPT_DIR%data\check_for_updates.log
pause
