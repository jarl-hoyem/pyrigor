$temporaryFile = Join-Path ([IO.Path]::GetTempPath()) "pyrigor-parse-error-$PID.py"

try
{
    # noinspection IncorrectFormatting
    Set-Content -Path $temporaryFile -Value "def broken(:`n    pass`n" -Encoding utf8
    uv run pyrigor --output-format=json $temporaryFile
    exit $LASTEXITCODE
}
finally
{
    # noinspection IncorrectFormatting
    Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
}
