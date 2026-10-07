<#
Removes the MaxxedBeats AI assistant installed by install.ps1 (or by
scripts/install_maxxedbeats.py): the MaxxedBeats Quark and ChaosOsc folders
in %LOCALAPPDATA%\SuperCollider\Extensions.

  powershell -ExecutionPolicy Bypass -File uninstall.ps1 [-ExtensionsDir DIR]

Only folders that carry the MaxxedBeats install marker are removed; if
either folder exists without its marker, nothing is removed. Projects,
renders, settings, and API keys (Windows Credential Manager) are kept.
#>
param([string]$ExtensionsDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$items = @(
    @{ Name = 'MaxxedBeats'; Marker = '.maxxedbeats-install-marker' },
    @{ Name = 'ChaosOsc'; Marker = '.chaososc-install-marker' }
)

if (-not $ExtensionsDir) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    $ExtensionsDir = Join-Path (Join-Path $localAppData 'SuperCollider') 'Extensions'
}
$ExtensionsDir = [IO.Path]::GetFullPath($ExtensionsDir)

foreach ($item in $items) {
    $target = Join-Path $ExtensionsDir $item.Name
    if ((Test-Path -LiteralPath $target) -and -not (Test-Path -LiteralPath (Join-Path $target $item.Marker) -PathType Leaf)) {
        [Console]::Error.WriteLine(('ERROR: refusing to uninstall: {0} has no {1} marker, so it was not installed by MaxxedBeats. Nothing was removed.' -f $target, $item.Marker))
        exit 1
    }
}
$removed = 0
foreach ($item in $items) {
    $target = Join-Path $ExtensionsDir $item.Name
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Output ('Removed {0}' -f $target)
        $removed++
    } else {
        Write-Output ('{0} is not installed at {1}.' -f $item.Name, $target)
    }
}
if ($removed -gt 0) {
    Write-Output ''
    Write-Output 'Next steps:'
    Write-Output '  1. Close the MaxxedBeats window, then recompile the class library:'
    Write-Output '     Language > Recompile Class Library (or evaluate thisProcess.recompile).'
    Write-Output '  2. Reboot the audio server so it unloads ChaosOsc: s.reboot'
    Write-Output '  API keys stay in Windows Credential Manager; remove them first from the'
    Write-Output '  assistant''s Keys & Privacy tab if you no longer need them.'
}
exit 0
