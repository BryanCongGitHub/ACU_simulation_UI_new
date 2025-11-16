@echo off
set PYTHONDONTWRITEBYTECODE=1
if "%~1"=="" (
  python -m pytest tests/test_protocol_parser.py
) else (
  python -m pytest %*
)
exit /b %errorlevel%
