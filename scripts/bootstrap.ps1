param(
  [switch]$NoLaunch,
  [ValidateSet('new','old')]
  [string]$Ui
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Join-Path -ChildPath '..' | Resolve-Path
Set-Location $Root

$py = "$Root\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = (Get-Command python -ErrorAction SilentlyContinue)?.Source
  if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue)?.Source }
}
if (-not $py) { Write-Error "Python not found. Install Python 3.10+"; exit 1 }

$argsList = @()
if ($NoLaunch) { $argsList += '--no-launch' }
if ($Ui) { $argsList += @('--ui', $Ui) }

& $py scripts/bootstrap.py @argsList

