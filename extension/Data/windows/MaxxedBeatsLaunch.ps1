<#
MaxxedBeats render-process launcher for Windows 10 (1803+) and 11
(PowerShell 5.1+). MBRenderProcess starts it with one argument, -Spec, the
path of a JSON file written next to the log:

  { "program": "C:\\...\\sclang.exe", "args": ["-l", "..."],
    "environment": { "NAME": "value", ... },
    "workingDirectory": "...", "log": "C:\\...\\sclang.log" }

The child runs with a cleared environment that holds only the listed
variables (nothing is inherited, so no secrets), stdin closed (like NUL), no
window, and stdout followed by stderr in the log file. Exits with the child's
exit code (126 if it could not be started). Stopping this process tree
(taskkill /T) also stops the child.
#>
param([Parameter(Mandatory = $true)][string]$Spec)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Quotes one argument for a Windows command line (CommandLineToArgvW rules).
function ConvertTo-CommandLineArgument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($char in $Value.ToCharArray()) {
        if ($char -eq [char]'\') { $slashes++; continue }
        if ($char -eq [char]'"') {
            [void]$builder.Append('\' * (2 * $slashes + 1)).Append('"')
        } else {
            [void]$builder.Append('\' * $slashes).Append($char)
        }
        $slashes = 0
    }
    [void]$builder.Append('\' * (2 * $slashes)).Append('"')
    return $builder.ToString()
}

$code = 126
$log = $null
$errorLog = $null
try {
    $settings = [IO.File]::ReadAllText($Spec) | ConvertFrom-Json
    $logPath = [string]$settings.log
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $log = New-Object IO.FileStream($logPath, [IO.FileMode]::Create, [IO.FileAccess]::Write, $share, 1)
    $errorLog = New-Object IO.MemoryStream
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = [string]$settings.program
    $info.Arguments = (@($settings.args) | ForEach-Object { ConvertTo-CommandLineArgument ([string]$_) }) -join ' '
    $info.WorkingDirectory = [string]$settings.workingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.EnvironmentVariables.Clear()
    foreach ($entry in $settings.environment.PSObject.Properties) {
        $info.EnvironmentVariables[$entry.Name] = [string]$entry.Value
    }
    $process = [System.Diagnostics.Process]::Start($info)
    $process.StandardInput.Close()
    $copyOut = $process.StandardOutput.BaseStream.CopyToAsync($log)
    $copyErr = $process.StandardError.BaseStream.CopyToAsync($errorLog)
    $process.WaitForExit()
    $copyOut.Wait()
    $copyErr.Wait()
    $errorLog.WriteTo($log)
    $code = $process.ExitCode
} catch {
    $message = [Text.Encoding]::UTF8.GetBytes("MaxxedBeats launcher: " + $_.Exception.Message + "`n")
    try { if ($null -ne $log) { $log.Write($message, 0, $message.Length) } } catch { }
    $code = 126
} finally {
    if ($null -ne $log) { $log.Dispose() }
}
exit $code
