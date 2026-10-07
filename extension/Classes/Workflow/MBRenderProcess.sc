/*
Runs one headless child process (sclang or scsynth) without a shell-visible
secret: the child gets a minimal, explicit environment, stdin from the null
device, and stdout/stderr in a log file. Enforces a timeout, can be
cancelled (the whole process tree), can stop early when a fatal pattern
appears in the log, and calls onExit(process) on AppClock exactly once.

POSIX: `exec env -i VAR=... argv < /dev/null > log 2>&1` through /bin/sh.
Windows: Data/windows/MaxxedBeatsLaunch.ps1 (PowerShell 5.1) reads a JSON
spec written next to the log (program, args, environment, log) and starts
the child with a cleared environment; no shell parses any path, so spaces,
backslashes, and cmd metacharacters in paths are safe. Kill = taskkill /T /F.
*/
MBRenderProcess {
	classvar <>pollInterval = 0.25;
	var <argv, <environment, <logPath, <timeout, onExit, failPatterns;
	var <pid, <exitCode, <timedOut = false, <cancelled = false, <finished = false, <failMatch;
	var startTime, poller, killing = false;

	*run { |argv, environment, logPath, timeout = 120, onExit, failPatterns|
		^super.newCopyArgs(argv, environment, logPath, timeout, onExit, failPatterns ? []).prRun
	}

	*quotePosix { |string| ^string.asString.shellQuote }

	*isWindows { ^thisProcess.platform.name == \windows }

	*launcherPath {
		^this.filenameSymbol.asString.dirname.dirname.dirname +/+ "Data" +/+ "windows" +/+ "MaxxedBeatsLaunch.ps1"
	}

	*specPath { |logPath| ^logPath.splitext[0] ++ "-launch.json" }

	// Windows: the launcher's JSON spec (no shell quoting involved).
	*windowsSpec { |argv, environment, logPath|
		var env = ();
		environment.keysValuesDo { |key, value| env[key.asSymbol] = value.asString };
		^(program: argv[0].asString, args: argv.drop(1).collect(_.asString), environment: env,
			workingDirectory: logPath.dirname, log: logPath)
	}

	// The command passed to unixCmd: a /bin/sh line on POSIX, an argv Array
	// (PowerShell launcher + spec path) on Windows.
	*commandLine { |argv, environment, logPath|
		var pairs = environment.keys.asArray.sort.collect { |key| [key.asString, environment[key].asString] };
		^if(this.isWindows) {
			[MBProviderPaths.powershellPath, "-NoLogo", "-NoProfile", "-NonInteractive", "-InputFormat", "None", "-ExecutionPolicy", "Bypass",
				"-File", this.launcherPath, "-Spec", this.specPath(logPath)]
		} {
			"exec env -i " ++ pairs.collect { |pair| this.quotePosix(pair[0] ++ "=" ++ pair[1]) }.join(" ")
			++ " " ++ argv.collect { |item| this.quotePosix(item) }.join(" ")
			++ " < /dev/null > " ++ this.quotePosix(logPath) ++ " 2>&1"
		}
	}

	*isolatedEnvironment { |home, tmp|
		var env = (
			HOME: home,
			XDG_CONFIG_HOME: home +/+ ".config",
			XDG_DATA_HOME: home +/+ ".local/share",
			XDG_CACHE_HOME: home +/+ ".cache",
			TMPDIR: tmp,
			LANG: "en_US.UTF-8"
		);
		if(this.isWindows) {
			env.putAll((
				USERPROFILE: home,
				APPDATA: home +/+ "AppData" +/+ "Roaming",
				LOCALAPPDATA: home +/+ "AppData" +/+ "Local",
				TEMP: tmp,
				TMP: tmp,
				SystemRoot: "SystemRoot".getenv ? "C:\\Windows",
				windir: "SystemRoot".getenv ? "C:\\Windows",
				PATH: [("SystemRoot".getenv ? "C:\\Windows") +/+ "System32", "SystemRoot".getenv ? "C:\\Windows"].join(";")
			));
		} {
			env[\PATH] = "/usr/bin:/bin:/usr/sbin:/sbin";
		};
		^env
	}

	prRun {
		var command = MBRenderProcess.commandLine(argv, environment, logPath), checkCounter = 0;
		File.mkdir(logPath.dirname);
		if(MBRenderProcess.isWindows) {
			MBProject.writeFile(MBRenderProcess.specPath(logPath),
				MBWorkflowJSON.stringify(MBRenderProcess.windowsSpec(argv, environment, logPath)));
		};
		startTime = Main.elapsedTime;
		pid = command.unixCmd({ |code| this.prExited(code) }, false);
		if(pid.isNil or: { pid <= 0 }) {
			AppClock.sched(0, { this.prExited(-1); nil });
			^this
		};
		poller = Routine {
			while { finished.not } {
				pollInterval.wait;
				if(finished.not) {
					if((Main.elapsedTime - startTime) > timeout) {
						timedOut = true;
						this.kill;
					} {
						checkCounter = checkCounter + 1;
						if(failPatterns.notEmpty and: { checkCounter % 4 == 0 }) { this.prScanLog };
					};
				};
			};
		}.play(AppClock);
	}

	prScanLog {
		var text = MBRenderProcess.readLog(logPath);
		failPatterns.do { |pattern|
			if(failMatch.isNil and: { text.contains(pattern) }) {
				failMatch = pattern;
				this.kill;
			}
		};
	}

	*readLog { |path, maxBytes = 262144|
		var text = MBWorkflowTry.value({ MBProject.readFile(path) });
		if(text.isString.not) { ^"" };
		^if(text.size > maxBytes) { text.copyRange(text.size - maxBytes, text.size - 1) } { text }
	}

	elapsed { ^Main.elapsedTime - startTime }

	kill {
		if(finished.not and: { killing.not } and: { pid.notNil } and: { pid > 0 }) {
			killing = true;
			if(MBRenderProcess.isWindows) {
				MBProviderPaths.killTree(pid)
			} {
				thisProcess.platform.killProcessByID(pid)
			};
		};
	}

	cancel {
		if(finished.not) {
			cancelled = true;
			this.kill;
		};
	}

	succeeded { ^finished and: { exitCode == 0 } and: { timedOut.not } and: { cancelled.not } and: { failMatch.isNil } }

	prExited { |code|
		if(finished.not) {
			finished = true;
			exitCode = code;
			if(poller.notNil and: { poller !== thisThread }) { poller.stop };
			AppClock.sched(0, { onExit.value(this); nil });
		};
	}
}

/*
Automatic, objective checks of a rendered file: format, duration,
non-finite samples, silence, and clipping. Reads in chunks on AppClock so
the language stays responsive. It never judges musical quality.
*/
MBAudioCheck {
	classvar <>chunkFrames = 32768;
	var <file, routine, cancelled = false;

	*analyze { |path, expected, onDone, silenceThresholdDb = -60, clipThreshold = 0.999|
		^super.new.init(path, expected, onDone, silenceThresholdDb, clipThreshold)
	}

	init { |path, expected, onDone, silenceThresholdDb, clipThreshold|
		routine = Routine {
			var outcome = try {
				protect {
					file = SoundFile.openRead(path);
					if(file.isNil) {
						MBError(\render, "the rendered file could not be opened as audio: " ++ path.basename)
					} {
						MBAudioCheck.prScan(file, expected, silenceThresholdDb, clipThreshold)
					}
				} {
					this.closeFile
				}
			} { |error| MBProject.asMBError(error, \render) };
			if(cancelled.not) { onDone.value(outcome) };
		};
		routine.play(AppClock);
		^this
	}

	closeFile {
		if(file.notNil and: { file.isOpen }) { file.close };
	}

	stop {
		cancelled = true;
		routine.stop;
		this.closeFile;
		^this
	}

	*prScan { |file, expected, silenceThresholdDb, clipThreshold|
		var frames = file.numFrames, channels = file.numChannels, sampleRate = file.sampleRate;
		var peak = 0.0, sumSquares = 0.0, nonFinite = 0, clippedSamples = 0, remaining, data, count = 0;
		var duration, tolerance, rms, checks, readOk = true;
		remaining = frames * channels;
		while { remaining > 0 and: { readOk } } {
			data = FloatArray.newClear(min(remaining, chunkFrames * channels));
			readOk = MBWorkflowTry.value({ file.readData(data); true }) == true and: { data.size > 0 };
			if(readOk) {
				data.do { |sample|
					var magnitude = sample.abs;
					if(magnitude < inf) {
						if(magnitude > peak) { peak = magnitude };
						if(magnitude >= clipThreshold) { clippedSamples = clippedSamples + 1 };
						sumSquares = sumSquares + (sample * sample);
					} {
						nonFinite = nonFinite + 1
					};
				};
				count = count + data.size;
				remaining = remaining - data.size;
				0.yield;
			};
		};
		if(count < (frames * channels)) {
			^MBError(\render, "the rendered file is truncated or unreadable: " ++ file.path.basename)
		};
		duration = if(sampleRate > 0) { frames / sampleRate } { 0 };
		tolerance = max(2 * 64 / max(sampleRate, 1), 0.002);
		rms = if(count > 0) { (sumSquares / max(count - nonFinite, 1)).sqrt } { 0.0 };
		checks = (
			rendered: true,
			finite: nonFinite == 0,
			silent: peak < silenceThresholdDb.dbamp,
			clipped: clippedSamples > 0,
			durationOk: (duration - expected[\duration]).abs <= tolerance,
			formatOk: sampleRate == expected[\sampleRate] and: { channels == expected[\numChannels] },
			peak: peak,
			peakDb: if(peak > 0) { peak.ampdb.round(0.01) } { -inf },
			rms: rms,
			rmsDb: if(rms > 0) { rms.ampdb.round(0.01) } { -inf },
			nonFiniteSamples: nonFinite,
			clippedSamples: clippedSamples
		);
		checks[\ok] = checks[\finite] and: { checks[\silent].not } and: { checks[\clipped].not }
			and: { checks[\durationOk] } and: { checks[\formatOk] };
		^(checks: checks, duration: duration, sampleRate: sampleRate, numChannels: channels)
	}
}
