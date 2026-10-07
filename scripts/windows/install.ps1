<#
Installs the MaxxedBeats AI assistant from MaxxedBeats-Windows-x64.zip:
copies the MaxxedBeats Quark (classes, help, agent instructions) and the
prebuilt ChaosOsc plugin into SuperCollider's user Extensions folder,
%LOCALAPPDATA%\SuperCollider\Extensions (SuperCollider's
Platform.userExtensionDir). No Python, CMake, or compiler is needed.

  powershell -ExecutionPolicy Bypass -File install.ps1 [-ExtensionsDir DIR]

Each installed folder gets a marker file. A MaxxedBeats or ChaosOsc folder
without that marker was not installed by MaxxedBeats and is never replaced;
both folders are checked before anything is changed. API keys are never
touched (they live in Windows Credential Manager).
#>
param([string]$ExtensionsDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$packageDir = $PSScriptRoot
$items = @(
    @{ Name = 'MaxxedBeats'; Marker = '.maxxedbeats-install-marker';
       Required = @('MaxxedBeats.quark', 'Classes\MaxxedBeats.sc', 'agent\ROLE.md', 'Data\windows\MaxxedBeatsCredential.ps1') },
    @{ Name = 'ChaosOsc'; Marker = '.chaososc-install-marker';
       Required = @('ChaosOsc.scx', 'Classes\ChaosOsc.sc') }
)

function Fail([string]$Message) {
    [Console]::Error.WriteLine('ERROR: ' + $Message)
    exit 1
}

if (-not $ExtensionsDir) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $ExtensionsDir = Join-Path (Join-Path $localAppData 'SuperCollider') 'Extensions'
}
$ExtensionsDir = [IO.Path]::GetFullPath($ExtensionsDir)

foreach ($item in $items) {
    foreach ($relative in $item.Required) {
        if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $packageDir $item.Name) $relative) -PathType Leaf)) {
            Fail ("this package is incomplete: {0}\{1} is missing. Extract the whole zip and run install.ps1 from the extracted folder." -f $item.Name, $relative)
        }
    }
}
foreach ($item in $items) {
    $target = Join-Path $ExtensionsDir $item.Name
    if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath (Join-Path $target $item.Marker) -PathType Leaf)) {
        Fail ("{0} already exists and was not installed by MaxxedBeats (no {1} marker). Nothing was changed. Move or delete that folder yourself if it is an old copy, then run install.ps1 again." -f $target, $item.Marker)
    }
}

Write-Output 'MaxxedBeats installer (Windows)'
Write-Output ('  Extensions folder: ' + $ExtensionsDir)
New-Item -ItemType Directory -Force -Path $ExtensionsDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
foreach ($item in $items) {
    $source = Join-Path $packageDir $item.Name
    $target = Join-Path $ExtensionsDir $item.Name
    $staging = Join-Path $ExtensionsDir ('.{0}.installing-{1}' -f $item.Name, $PID)
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    try {
        Copy-Item -LiteralPath $source -Destination $staging -Recurse -Force
        # Files extracted from a downloaded zip carry the mark of the web.
        if (Get-Command Unblock-File -ErrorAction SilentlyContinue) {
            Get-ChildItem -LiteralPath $staging -Recurse -File | Unblock-File
        }
        $marker = "{0} installed by install.ps1 from MaxxedBeats-Windows-x64.zip.`r`nRe-running install.ps1 may replace this folder, and uninstall.ps1 may remove it.`r`nsource: {1}`r`ninstalled: {2}`r`n" -f $item.Name, $packageDir, $stamp
        [IO.File]::WriteAllText((Join-Path $staging $item.Marker), $marker)
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Move-Item -LiteralPath $staging -Destination $target
    } finally {
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
    Write-Output ('  Installed {0} to {1}' -f $item.Name, $target)
}

$programData = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
foreach ($root in @($ExtensionsDir, (Join-Path (Join-Path $programData 'SuperCollider') 'Extensions'))) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($class in @('MaxxedBeats.sc', 'ChaosOsc.sc')) {
        Get-ChildItem -LiteralPath $root -Recurse -File -Filter $class -ErrorAction SilentlyContinue | ForEach-Object {
            $owner = if ($class -eq 'MaxxedBeats.sc') { 'MaxxedBeats' } else { 'ChaosOsc' }
            if (-not $_.FullName.StartsWith((Join-Path $ExtensionsDir $owner) + '\', [StringComparison]::OrdinalIgnoreCase)) {
                Write-Output ('WARNING: another copy exists at {0}; remove it, or SuperCollider reports duplicate classes.' -f $_.FullName)
            }
        }
    }
}

Write-Output ''
Write-Output 'Next steps:'
Write-Output '  1. Start SuperCollider (SCIDE). If it was already open, recompile the class library:'
Write-Output '     Language > Recompile Class Library (or evaluate thisProcess.recompile).'
Write-Output '  2. Reboot the audio server so it loads ChaosOsc: s.reboot'
Write-Output '  3. Open the assistant: MaxxedBeats.gui'
Write-Output '     (help: search the SCIDE help browser for "MaxxedBeats").'
exit 0
