<#
Set up the optional GitHub Copilot provider from the installed MaxxedBeats
extension. WinGet installs the official CLI and Python only when they are
missing; the Python helper creates a private, pinned SDK environment.
#>
param(
    [string]$ExtensionsDir,
    [string]$PythonExecutable,
    [string]$CopilotCliPath,
    [switch]$SkipPackageInstall,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Fail([string]$Message) {
    [Console]::Error.WriteLine('ERROR: ' + $Message)
    exit 1
}

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machinePath, $userPath, $env:Path) | Where-Object { $_ }) -join ';'
}

function Find-Python {
    if ($PythonExecutable) {
        return [PSCustomObject]@{ Executable = $PythonExecutable; Prefix = @() }
    }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @('3.13', '3.12', '3.11')) {
            & $launcher.Source ('-' + $version) -c 'import sys; print(sys.executable)' *> $null
            if ($LASTEXITCODE -eq 0) {
                return [PSCustomObject]@{ Executable = $launcher.Source; Prefix = @('-' + $version) }
            }
        }
    }

    foreach ($name in @('python3.13.exe', 'python3.12.exe', 'python3.11.exe', 'python.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        if ($command.Source -like '*\Microsoft\WindowsApps\python.exe') { continue }
        $version = & $command.Source -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 11) {
            return [PSCustomObject]@{ Executable = $command.Source; Prefix = @() }
        }
    }
    return $null
}

function Find-CopilotCli {
    if ($CopilotCliPath) { return $CopilotCliPath }
    $command = Get-Command copilot.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\GitHub Copilot\copilot.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\copilot.exe'),
        (Join-Path $env:APPDATA 'npm\node_modules\@github\copilot\node_modules\@github\copilot-win32-x64\copilot.exe'),
        (Join-Path $HOME '.local\copilot-cli\lib\node_modules\@github\copilot\node_modules\@github\copilot-win32-x64\copilot.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

if (-not $ExtensionsDir) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $ExtensionsDir = Join-Path (Join-Path $localAppData 'SuperCollider') 'Extensions'
}
$setupScript = Join-Path (Join-Path (Join-Path $ExtensionsDir 'MaxxedBeats') 'Data\copilot') 'setup_copilot.py'
if (-not (Test-Path -LiteralPath $setupScript -PathType Leaf)) {
    Fail 'The Copilot setup helper is missing. Reinstall MaxxedBeats from the complete Windows zip.'
}

if ($DryRun) {
    if (-not $PythonExecutable -or -not $CopilotCliPath) {
        Fail 'DryRun requires both PythonExecutable and CopilotCliPath.'
    }
    Write-Output ('Would run: {0} {1} --cli-path {2}' -f $PythonExecutable, $setupScript, $CopilotCliPath)
    exit 0
}

if (-not $SkipPackageInstall) {
    Write-Output 'This optional step installs Python 3.13 and the official GitHub Copilot CLI if needed.'
    Write-Output 'WinGet may ask Windows to confirm an installation. No API key is requested.'
    $answer = Read-Host 'Continue with GitHub Copilot setup? [Y/n]'
    if ($answer -match '^[Nn]') {
        Write-Output 'Copilot setup skipped. Mock DJ, OpenAI, and Anthropic remain available.'
        exit 0
    }

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Start-Process 'https://aka.ms/getwinget' -ErrorAction SilentlyContinue
        Fail 'WinGet is not available. Install Microsoft App Installer from https://aka.ms/getwinget, then double-click Install-MaxxedBeats.cmd again.'
    }

    $python = Find-Python
    if (-not $python) {
        Write-Output 'Installing Python 3.13 for the private Copilot runtime...'
        & $winget.Source install --id Python.Python.3.13 --exact --source winget `
            --scope user --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) { Fail 'WinGet could not install Python 3.13. Retry or use the official Python installer from python.org.' }
        Refresh-Path
        $python = Find-Python
    }
    if (-not $python) { Fail 'Python 3.11 or newer was not found after installation. Restart Windows and run setup again.' }

    $CopilotCliPath = Find-CopilotCli
    if (-not $CopilotCliPath) {
        Write-Output 'Installing the official GitHub Copilot CLI...'
        & $winget.Source install --id GitHub.Copilot --exact --source winget `
            --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) { Fail 'WinGet could not install the GitHub Copilot CLI. Retry or use GitHub''s official CLI install page.' }
        Refresh-Path
        $CopilotCliPath = Find-CopilotCli
    }
} else {
    $python = Find-Python
}

if (-not $python) { Fail 'Python 3.11 or newer is required to finish Copilot setup.' }
if (-not $CopilotCliPath) { $CopilotCliPath = Find-CopilotCli }

$arguments = @($python.Prefix) + @($setupScript)
if ($CopilotCliPath) { $arguments += @('--cli-path', $CopilotCliPath) }
Write-Output 'Installing the private Copilot SDK runtime...'
& $python.Executable @arguments
if ($LASTEXITCODE -ne 0) { Fail 'The Copilot SDK setup failed. Check your internet connection and run setup again.' }

Write-Output ''
Write-Output 'Copilot setup is complete.'
Write-Output 'In MaxxedBeats choose GitHub Copilot, open Keys & Privacy, and click the Copilot sign-in button.'
Write-Output 'Finish sign-in in your browser, then refresh models.'
exit 0
