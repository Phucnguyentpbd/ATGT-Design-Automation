param(
    [string]$LibraryPath = 'D:\DOCUMENT\TAI LIEU AUTOCAD\Tool CAD\lispCAD\0. Hay dung\AtgtPro\Library',
    [string]$Output = 'local-manifests\atgt-signs.json',
    [string]$ReviewOutput = 'local-manifests\atgt-review-queue.json'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $LibraryPath -PathType Container)) {
    throw "CAD library is not available: $LibraryPath"
}
$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($python) {
    & py -m atgt.inventory_cli --sign-library "$LibraryPath" --output "$Output" --expected "data/source-locks/sign-library-summary.json" --review-output "$ReviewOutput"
} else {
    & python -m atgt.inventory_cli --sign-library "$LibraryPath" --output "$Output"
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Source lock verified; metadata-only inventory written to $Output"
Write-Host "DWG review queue written to $ReviewOutput"
Write-Host "DWG source files have not been copied or modified."
