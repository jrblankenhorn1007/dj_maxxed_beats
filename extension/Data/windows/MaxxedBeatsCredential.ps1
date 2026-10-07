<#
MaxxedBeats helper for Windows 10 (1803+) and 11: Windows Credential Manager
(generic credentials, CredRead/CredWrite/CredDelete) and the curl.exe
request runner. PowerShell 5.1+.

Started by MBProcess (sclang) through Pipe.argv with -InputFormat None, so
its stdin is a pipe from sclang that only this script reads (one line). It
prints nothing; results go to files in the private run directory:
stderr.txt (an error message without secrets) and, written last,
exit-code.txt (the exit code). sclang polls for exit-code.txt.

  -Action has     -Target T            exit 0 if stored, 1 if not
  -Action store   -Target T            reads the key (one line) from stdin
  -Action remove  -Target T            deletes it (absent is not an error)
  -Action request [-Target T | -KeyFromStdin]
        runs curl.exe as described by <RunDir>\curl-spec.json
        ({curl, args: [...], headerPrefix}) with <RunDir> as its working
        directory. With a headerPrefix, the key is read from the credential
        (or one stdin line) and only written to curl's stdin as the config
        line   header = "<prefix><key>"   (curl -K -). Exit: curl's exit
        code, or 120 no key, 121 malformed key, 122 curl.exe not found.

The key never appears in arguments, environment variables, files, or output.
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet('has', 'store', 'remove', 'request')][string]$Action,
    [Parameter(Mandatory = $true)][string]$RunDir,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9:._-]{0,199}$')][string]$Target,
    [switch]$KeyFromStdin
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$keyPattern = '^[A-Za-z0-9][A-Za-z0-9_.-]{7,511}$'

function Add-CredentialApi {
    if ('MBCred' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class MBCred {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct CREDENTIAL {
        public int Flags; public int Type; public string TargetName; public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public int CredentialBlobSize; public IntPtr CredentialBlob; public int Persist;
        public int AttributeCount; public IntPtr Attributes; public string TargetAlias; public string UserName;
    }
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CredReadW(string target, int type, int flags, out IntPtr cred);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CredWriteW(ref CREDENTIAL cred, int flags);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CredDeleteW(string target, int type, int flags);
    [DllImport("advapi32.dll")]
    static extern void CredFree(IntPtr cred);
    const int GENERIC = 1, PERSIST_LOCAL_MACHINE = 2, ERROR_NOT_FOUND = 1168;

    public static string Read(string target) {
        IntPtr p;
        if (!CredReadW(target, GENERIC, 0, out p)) {
            int error = Marshal.GetLastWin32Error();
            if (error == ERROR_NOT_FOUND) return null;
            throw new System.ComponentModel.Win32Exception(error);
        }
        try {
            CREDENTIAL c = (CREDENTIAL)Marshal.PtrToStructure(p, typeof(CREDENTIAL));
            byte[] blob = new byte[c.CredentialBlobSize];
            Marshal.Copy(c.CredentialBlob, blob, 0, blob.Length);
            return Encoding.UTF8.GetString(blob);
        } finally { CredFree(p); }
    }
    public static void Write(string target, string user, string comment, string secret) {
        byte[] blob = Encoding.UTF8.GetBytes(secret);
        CREDENTIAL c = new CREDENTIAL();
        c.Type = GENERIC; c.TargetName = target; c.UserName = user; c.Comment = comment;
        c.Persist = PERSIST_LOCAL_MACHINE; c.CredentialBlobSize = blob.Length;
        c.CredentialBlob = Marshal.AllocHGlobal(blob.Length);
        try {
            Marshal.Copy(blob, 0, c.CredentialBlob, blob.Length);
            if (!CredWriteW(ref c, 0)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        } finally {
            Marshal.Copy(new byte[blob.Length], 0, c.CredentialBlob, blob.Length);
            Marshal.FreeHGlobal(c.CredentialBlob);
        }
    }
    public static bool Delete(string target) {
        if (CredDeleteW(target, GENERIC, 0)) return true;
        return Marshal.GetLastWin32Error() == ERROR_NOT_FOUND;
    }
}
'@
}

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

# One line from the raw stdin handle (sclang's pipe). PowerShell is started
# with -InputFormat None, so the host itself never reads or waits for stdin.
function Read-StdinLine {
    $stream = [Console]::OpenStandardInput()
    $buffer = New-Object System.IO.MemoryStream
    while ($buffer.Length -lt 1024) {
        $next = $stream.ReadByte()
        if ($next -lt 0 -or $next -eq 10) { break }
        $buffer.WriteByte([byte]$next)
    }
    $line = [Text.Encoding]::ASCII.GetString($buffer.ToArray()).Trim()
    $buffer.SetLength(0)
    return $line
}

function Require-Target {
    if (-not $Target) { throw 'a credential target is required' }
}

function Invoke-Request {
    $spec = [IO.File]::ReadAllText((Join-Path $RunDir 'curl-spec.json')) | ConvertFrom-Json
    $curl = [string]$spec.curl
    if ([IO.Path]::IsPathRooted($curl)) {
        if (-not (Test-Path -LiteralPath $curl -PathType Leaf)) { return 122 }
    } else {
        $found = Get-Command -Name $curl -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $found) { return 122 }
        $curl = $found.Source
    }
    $config = ''
    if ($spec.headerPrefix) {
        if ($KeyFromStdin) {
            $key = Read-StdinLine
        } else {
            Require-Target
            Add-CredentialApi
            $key = [MBCred]::Read($Target)
        }
        if ([string]::IsNullOrEmpty($key)) { return 120 }
        if ($key -cnotmatch $keyPattern) { return 121 }
        $config = 'header = "' + [string]$spec.headerPrefix + $key + '"' + "`n"
        $key = $null
    }
    # .NET Framework writes Console.InputEncoding's preamble (a UTF-8 BOM when
    # the console code page is 65001) into a redirected stdin, which would
    # corrupt curl's config line; use an encoding without one.
    try { [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
    if ([Console]::InputEncoding.GetPreamble().Length -gt 0) {
        throw 'the console input encoding adds a byte order mark; cannot pass the key to curl'
    }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $curl
    $info.Arguments = (@($spec.args) | ForEach-Object { ConvertTo-CommandLineArgument ([string]$_) }) -join ' '
    $info.WorkingDirectory = $RunDir
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardInput = $true
    $process = [System.Diagnostics.Process]::Start($info)
    $bytes = [Text.Encoding]::ASCII.GetBytes($config)
    $config = $null
    $stdin = $process.StandardInput.BaseStream
    $stdin.Write($bytes, 0, $bytes.Length)
    $stdin.Flush()
    $process.StandardInput.Close()
    [Array]::Clear($bytes, 0, $bytes.Length)
    $process.WaitForExit()
    return $process.ExitCode
}

function Invoke-Action {
    switch ($Action) {
        'has' {
            Require-Target
            Add-CredentialApi
            if ($null -ne [MBCred]::Read($Target)) { return 0 } else { return 1 }
        }
        'store' {
            Require-Target
            $key = Read-StdinLine
            if ($key -cnotmatch $keyPattern) { throw 'the key has an invalid format' }
            Add-CredentialApi
            $account = ($Target -split ':')[-1]
            [MBCred]::Write($Target, $account, 'MaxxedBeats API key', $key)
            $key = $null
            return 0
        }
        'remove' {
            Require-Target
            Add-CredentialApi
            if ([MBCred]::Delete($Target)) { return 0 } else { return 1 }
        }
        'request' { return (Invoke-Request) }
    }
}

$code = 125
try {
    $code = [int](Invoke-Action)
} catch {
    $code = 125
    try {
        [IO.File]::WriteAllText((Join-Path $RunDir 'stderr.txt'), [string]$_.Exception.Message)
    } catch { }
} finally {
    try {
        $partial = Join-Path $RunDir 'exit-code.tmp'
        [IO.File]::WriteAllText($partial, [string]$code)
        Move-Item -LiteralPath $partial -Destination (Join-Path $RunDir 'exit-code.txt') -Force
    } catch { }
}
exit $code
