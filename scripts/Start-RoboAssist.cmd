@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-RoboAssist.ps1" -StartApplication
if errorlevel 1 pause

