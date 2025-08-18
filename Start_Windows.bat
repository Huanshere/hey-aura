@echo off
if exist "python_env\python.exe" (
    echo Using python_env\python.exe
    call python_env\python.exe app.py
) else (
    echo Using Conda environment hey-aura
    call conda activate hey-aura
    python app.py
)
pause