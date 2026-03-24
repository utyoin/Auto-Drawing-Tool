$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $projectRoot
try {
    python -m PyInstaller --noconfirm --clean Auto-drawpic.spec
}
finally {
    Pop-Location
}
