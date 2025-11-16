Param(
    [string[]]$TestTargets = @("tests/test_protocol_parser.py")
)

if (-not $TestTargets -or $TestTargets.Count -eq 0) {
    $TestTargets = @("tests/test_protocol_parser.py")
}

$old = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE = '1'
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
}
