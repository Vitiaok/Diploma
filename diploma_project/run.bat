@echo off
set PYTHONPATH=%CD%
if exist ..\..\python\python.exe (
    echo Starting using portable Python...
    start ..\..\python\python.exe app.py
) else (
    echo Starting using system Python...
    start python app.py
)
