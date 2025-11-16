Param(
    [string[]]$TestTargets = @(
        "tests/test_ui_integration.py",
        "tests/test_smoke_send_pytest.py",
        "tests/test_smoke_receive_pytest.py"
    )
)

if (-not $TestTargets -or $TestTargets.Count -eq 0) {
    $TestTargets = @("tests/test_protocol_parser.py")
}

$old = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE = '1'
# Disable pytest plugin autoload to avoid issues writing plugin cache in some environments
$oldPytestDisable = $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
try {
    # Ensure project root is on PYTHONPATH so tests can import local modules
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $env:PYTHONPATH = $repoRoot
    Write-Verbose "PYTHONPATH set to $repoRoot"
}
catch {
    # fallback to current directory
    $env:PYTHONPATH = (Get-Location).Path
}
try {
    python -m pytest @TestTargets
}
finally {
    if ($null -ne $old) {
        $env:PYTHONDONTWRITEBYTECODE = $old
    }
    else {
        Remove-Item env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    }
    if ($null -ne $oldPytestDisable) {
        $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = $oldPytestDisable
    }
    else {
        Remove-Item env:PYTEST_DISABLE_PLUGIN_AUTOLOAD -ErrorAction SilentlyContinue
    }
}
