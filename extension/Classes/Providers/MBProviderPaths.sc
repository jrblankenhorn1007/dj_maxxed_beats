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
		if(purged.not and: { this.isWindows.not }) {
			// Leftovers from a crashed session; never touches in-flight requests.
			["/usr/bin/find", base, "-mindepth", "1", "-maxdepth", "1", "-name", "req-*",
				"-mmin", "+120", "-exec", "/bin/rm", "-rf", "{}", "+"].unixCmd(nil, false);
			purged = true;
		};
		path = base +/+ ("req-" ++ Date.getDate.stamp ++ "-" ++ 1000000.rand
			++ "-" ++ UniqueID.next);
		File.mkdir(path);
		^path
	}

	*removeDir { |path|
		if(path.isNil or: { path.contains(this.runDir).not }) { ^this };
		if(this.isWindows) {
			("rmdir /s /q \"" ++ path ++ "\"").unixCmd(nil, false)
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
