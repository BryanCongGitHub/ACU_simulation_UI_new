@echo off
set PYTHONDONTWRITEBYTECODE=1
:: Ensure project root is on PYTHONPATH so tests can import local modules
set PYTHONPATH=%~dp0
if "%~1"=="" (
  python -m pytest tests/test_protocol_parser.py
) else (
  python -m pytest %*
)
exit /b %errorlevel%
