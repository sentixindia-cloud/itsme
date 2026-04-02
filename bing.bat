@echo off
REM Step 1: Run PowerShell command to set execution policy
echo Setting PowerShell Execution Policy...
powershell.exe -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force"

REM Step 2: Run the Python script
echo Running Python script to generate search keywords...
python generate_keys.py

timeout /t 5 /nobreak >nul

REM Step 3: Run the search PowerShell script
echo Running PowerShell script for Bing search ...
powershell.exe -ExecutionPolicy Bypass -File search.ps1

echo All tasks completed.
pause
