<#
MaxxedBeats credential helper for Windows Credential Manager (generic credentials).
Invoked by MBWindowsCredentialStore; never prints a key except as the single
curl config line requested by "curlconfig", which is piped straight into curl's
stdin and never written to disk.

  has <account>                       exit 0 if stored, 1 if not
  store <account>                     reads the key from stdin
  remove <account>                    deletes (absent key is not an error)
  curlconfig <account> <headerPrefix> prints: header = "<prefix><key>"

Status: designed for Windows 10+ (PowerShell 5.1); not yet runtime-verified.
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet('has', 'store', 'remove', 'curlconfig')][string]$Command,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z]+$')][string]$Account,
    [string]$HeaderPrefix = 'Authorization: Bearer '
)
$ErrorActionPreference = 'Stop'
$target = "MaxxedBeats:$Account"
$keyPattern = '^[A-Za-z0-9][A-Za-z0-9_.-]{7,511}$'

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
    const int GENERIC = 1, PERSIST_LOCAL_MACHINE = 2;

    public static string Read(string target) {
        IntPtr p;
        if (!CredReadW(target, GENERIC, 0, out p)) return null;
        try {
            CREDENTIAL c = (CREDENTIAL)Marshal.PtrToStructure(p, typeof(CREDENTIAL));
            byte[] blob = new byte[c.CredentialBlobSize];
            Marshal.Copy(c.CredentialBlob, blob, 0, blob.Length);
            return Encoding.UTF8.GetString(blob);
        } finally { CredFree(p); }
    }
    public static void Write(string target, string user, string secret) {
        byte[] blob = Encoding.UTF8.GetBytes(secret);
        CREDENTIAL c = new CREDENTIAL();
        c.Type = GENERIC; c.TargetName = target; c.UserName = user;
        c.Persist = PERSIST_LOCAL_MACHINE; c.CredentialBlobSize = blob.Length;
        c.CredentialBlob = Marshal.AllocHGlobal(blob.Length);
        try {
            Marshal.Copy(blob, 0, c.CredentialBlob, blob.Length);
            if (!CredWriteW(ref c, 0)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        } finally { Marshal.FreeHGlobal(c.CredentialBlob); }
    }
    public static bool Delete(string target) {
        if (CredDeleteW(target, GENERIC, 0)) return true;
        return Marshal.GetLastWin32Error() == 1168; // ERROR_NOT_FOUND
    }
}
'@

switch ($Command) {
    'has' { if ($null -ne [MBCred]::Read($target)) { exit 0 } else { exit 1 } }
    'store' {
        $key = [Console]::In.ReadToEnd().Trim()
        if ($key -notmatch $keyPattern) { [Console]::Error.WriteLine('invalid key format'); exit 2 }
        [MBCred]::Write($target, $Account, $key)
        exit 0
    }
    'remove' { if ([MBCred]::Delete($target)) { exit 0 } else { exit 1 } }
    'curlconfig' {
        $key = [MBCred]::Read($target)
        if ($null -eq $key -or $key -notmatch $keyPattern) { exit 120 }
        [Console]::Out.Write('header = "' + $HeaderPrefix + $key + '"' + "`n")
        exit 0
    }
}
