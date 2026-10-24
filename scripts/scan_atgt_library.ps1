param(
    [string]$LibraryPath = 'D:\DOCUMENT\TAI LIEU AUTOCAD\Tool CAD\lispCAD\0. Hay dung\AtgtPro\Library',
    [string]$Output = 'local-manifests\atgt-signs.json'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $LibraryPath -PathType Container)) {
    throw "CAD library is not available: $LibraryPath"
}
$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($python) {
    & py -m atgt.inventory_cli --sign-library "$LibraryPath" --output "$Output"
} else {
    & python -m atgt.inventory_cli --sign-library "$LibraryPath" --output "$Output"
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Metadata-only inventory written to $Output"
Write-Host "DWG source files have not been copied or modified."
