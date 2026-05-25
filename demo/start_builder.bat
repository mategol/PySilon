@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv venv || python -m venv venv || goto error
)

call "venv\Scripts\activate.bat" || goto error

echo Installing requirements...
python -m pip install --upgrade pip || goto error
python -m pip install -r requirements.txt || goto error
cls

python builder.py
pause
exit /b 0

:error
echo Failed to prepare or start the builder.
pause
exit /b 1
