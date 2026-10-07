// Locations and small file helpers for the provider layer. Only non-secret
// data is written here (settings, model cache, usage history, and per-request
// scratch directories that never contain API keys).
MBProviderPaths {
	classvar <>settingsDirOverride, purged = false, ensured;

	*isWindows { ^thisProcess.platform.name == \windows }

	*settingsDir {
		^settingsDirOverride ?? { Platform.userConfigDir +/+ "MaxxedBeats" }
	}

	*dataDir {
		^PathName(this.filenameSymbol.asString).pathOnly.withoutTrailingSlash
			.dirname.dirname +/+ "Data"
	}

	*runDir { ^this.settingsDir +/+ "run" }

	// Windows tools are taken from %SystemRoot%\System32 so that a program
	// of the same name earlier on PATH is never used.
	*windowsTool { |relativePath|
		var path = ("SystemRoot".getenv ? "C:\\Windows") +/+ "System32" +/+ relativePath;
		^if(File.exists(path)) { path } { relativePath.basename }
	}

	*powershellPath { ^this.windowsTool("WindowsPowerShell\\v1.0\\powershell.exe") }

	*windowsHelperPath { ^this.dataDir +/+ "windows" +/+ "MaxxedBeatsCredential.ps1" }

	// argv for Data/windows/MaxxedBeatsCredential.ps1; "@RUNDIR@" is replaced
	// by MBProcess with the private run directory.
	*windowsHelperArgv { |action, extra|
		^[this.powershellPath, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
			"-File", this.windowsHelperPath, "-Action", action, "-RunDir", "@RUNDIR@"] ++ (extra ? [])
	}

	// Stops a Windows process and everything it started (taskkill /T).
	*killTree { |pid|
		if(pid.notNil and: { pid > 0 }) {
			[this.windowsTool("taskkill.exe"), "/F", "/T", "/PID", pid.asString].unixCmd(nil, false)
		}
	}

	// Create a directory readable only by the current user.
	*ensurePrivateDir { |path|
		ensured = ensured ?? { Set.new };
		if(ensured.includes(path) and: { File.exists(path) }) { ^path };
		ensured.add(path);
		if(this.isWindows) {
			if(File.exists(path).not) { File.mkdir(path) };
		} {
			("umask 077; mkdir -p " ++ path.shellQuote ++ " && chmod 700 "
				++ path.shellQuote).systemCmd;
		};
		^path
	}

	*newRunDir {
		var base = this.ensurePrivateDir(this.runDir), path;
		if(purged.not) {
			// Leftovers from a crashed session; never touches in-flight requests.
			if(this.isWindows) {
				this.prPurgeWindows(base)
			} {
				["/usr/bin/find", base, "-mindepth", "1", "-maxdepth", "1", "-name", "req-*",
					"-mmin", "+120", "-exec", "/bin/rm", "-rf", "{}", "+"].unixCmd(nil, false);
			};
			purged = true;
		};
		path = base +/+ ("req-" ++ Date.getDate.stamp ++ "-" ++ 1000000.rand
			++ "-" ++ UniqueID.next);
		File.mkdir(path);
		^path
	}

	*prPurgeWindows { |base|
		var cutoff = Date.getDate.rawSeconds - 7200;
		PathName(base).folders.do { |folder|
			var path = folder.fullPath.withoutTrailingSlash;
			if(path.basename.beginsWith("req-") and: { File.mtime(path) < cutoff }) {
				this.removeDir(path)
			}
		}
	}

	*removeDir { |path, attempts = 4|
		if(path.isNil or: { path.contains(this.runDir).not }) { ^this };
		if(this.isWindows) {
			// A just-killed child may still hold the folder; retry briefly.
			[this.windowsTool("cmd.exe"), "/d", "/c", "rmdir", "/s", "/q", path].unixCmd({
				{
					if(File.exists(path) and: { attempts > 1 }) {
						AppClock.sched(1, { this.removeDir(path, attempts - 1); nil })
					}
				}.defer
			}, false)
		} {
			["/bin/rm", "-rf", path].unixCmd(nil, false)
		}
	}

	*readJSON { |path|
		var text;
		if(File.exists(path).not) { ^nil };
		^try {
			text = File.readAllString(path);
			MBJSON.parse(text)
		} { nil }
	}

	*writeJSON { |path, object|
		var file, temp = path ++ ".tmp";
		this.ensurePrivateDir(path.dirname);
		file = File(temp, "w");
		if(file.isOpen.not) { ^MBError(\io, "Could not write " ++ path) };
		file.write(MBJSON.encode(object) ++ "\n");
		file.close;
		if(File.exists(path)) { File.delete(path) };
		File.copy(temp, path);
		File.delete(temp);
		^nil
	}

	*writeText { |path, text|
		var file = File(path, "w");
		if(file.isOpen.not) { ^MBError(\io, "Could not write a request file") };
		file.write(text);
		file.close;
		^nil
	}

	*readText { |path|
		if(File.exists(path).not) { ^"" };
		^File.readAllString(path)
	}
}
