function Assert-Equal
{
    param(
        [AllowEmptyString()][string]$Actual,
        [AllowEmptyString()][string]$Expected,
        [string]$Message
    )

    if ($Actual -ne $Expected)
    {
        throw "$Message`nExpected: $Expected`nActual: $Actual"
    }
}

function Invoke-Pyrigor
{
    param([string[]]$Arguments)

    $output = & uv run pyrigor @Arguments 2>&1 | Out-String
    return [PSCustomObject]@{
        ExitCode = $LASTEXITCODE
        Output = $output
    }
}

function Test-Fix
{
    param(
        [string]$Path,
        [byte[]]$Original,
        [string]$Name
    )

    [IO.File]::WriteAllBytes($Path, $Original)
    $diff = Invoke-Pyrigor @("--diff", "--select=PYR402", $Path)
    Assert-Equal $diff.ExitCode 0 "$Name diff exit status"
    Assert-Equal ([Convert]::ToBase64String([IO.File]::ReadAllBytes($Path))) ([Convert]::ToBase64String($Original)) "$Name diff preserves the file"

    $fix = Invoke-Pyrigor @("--fix", "--show-fixes", "--select=PYR402", $Path)
    Assert-Equal $fix.ExitCode 0 "$Name fix exit status"
    if ($fix.Output -notmatch [Regex]::Escape([IO.Path]::GetFileName($Path)))
    {
        throw "$Name changed-file reporting did not name the file."
    }

    $expected = [Text.Encoding]::UTF8.GetBytes(
        ([Text.Encoding]::UTF8.GetString($Original)).Replace("def apply(left, right)", "def apply(*, left, right)")
    )
    Assert-Equal ([Convert]::ToBase64String([IO.File]::ReadAllBytes($Path))) ([Convert]::ToBase64String($expected)) "$Name preserves its original bytes"
}

$temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) "pyrigor-fix-pyr402-$PID"

try
{
    New-Item -ItemType Directory -Path $temporaryDirectory -ErrorAction Stop | Out-Null

    $normal = Join-Path $temporaryDirectory "normal.py"
    $normalSource = [Text.Encoding]::UTF8.GetBytes("def apply(left, right):`n    return left + right`n")
    Test-Fix -Path $normal -Original $normalSource -Name "LF"

    $bom = Join-Path $temporaryDirectory "bom.py"
    $bomSource = [Text.Encoding]::UTF8.GetPreamble() + [Text.Encoding]::UTF8.GetBytes("def apply(left, right):`n    ...`n")
    Test-Fix -Path $bom -Original $bomSource -Name "UTF-8 BOM"

    $crlf = Join-Path $temporaryDirectory "crlf.py"
    $crlfSource = [Text.Encoding]::UTF8.GetBytes("def apply(left, right):`r`n    ...`r`n")
    Test-Fix -Path $crlf -Original $crlfSource -Name "CRLF"

    $mixed = Join-Path $temporaryDirectory "mixed.py"
    $mixedSource = [Text.Encoding]::UTF8.GetBytes("# first`r`ndef apply(left, right):`n    ...`r`n# last`n")
    Test-Fix -Path $mixed -Original $mixedSource -Name "mixed line endings"

    $rejected = Join-Path $temporaryDirectory "rejected.py"
    $rejectedSource = "def apply(left, right, /):`n    ...`n"
    [IO.File]::WriteAllText($rejected, $rejectedSource,[Text.UTF8Encoding]::new($false))
    $rejectedResult = Invoke-Pyrigor @("--fix", "--select=PYR402", $rejected)
    Assert-Equal $rejectedResult.ExitCode 0 "rejected signature exit status"
    Assert-Equal ([IO.File]::ReadAllText($rejected)) $rejectedSource "rejected signature remains unchanged"

    $variadic = Join-Path $temporaryDirectory "variadic.py"
    $variadicSource = "def apply(left, right, *rest):`n    ...`n"
    [IO.File]::WriteAllText($variadic, $variadicSource,[Text.UTF8Encoding]::new($false))
    $variadicResult = Invoke-Pyrigor @("--fix", "--select=PYR402", $variadic)
    Assert-Equal $variadicResult.ExitCode 0 "variadic signature exit status"
    Assert-Equal ([IO.File]::ReadAllText($variadic)) $variadicSource "variadic signature remains unchanged"

    $missing = Join-Path $temporaryDirectory "missing.py"
    $missingResult = Invoke-Pyrigor @("--fix", "--select=PYR402", $missing)
    Assert-Equal $missingResult.ExitCode 0 "missing-file exit status"

    $invalidResult = Invoke-Pyrigor @("--fix", $normal)
    Assert-Equal $invalidResult.ExitCode 2 "missing-selection exit status"

    Write-Host "PYR402 manual fixer checks completed."
}
finally
{
    Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
}
