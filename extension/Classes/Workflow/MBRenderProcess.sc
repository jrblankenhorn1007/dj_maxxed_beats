/*
Runs one headless child process (sclang or scsynth) without a shell-visible
secret: the child gets a minimal, explicit environment (env -i on POSIX),
stdin from the null device, and stdout/stderr in a log file. Enforces a
timeout, can be cancelled, can stop early when a fatal pattern appears in
the log, and calls onExit(process) on AppClock exactly once.
*/
MBRenderProcess {
	classvar <>pollInterval = 0.25;
	var <argv, <environment, <logPath, <timeout, onExit, failPatterns;
	var <pid, <exitCode, <timedOut = false, <cancelled = false, <finished = false, <failMatch;
	var startTime, poller;

	*run { |argv, environment, logPath, timeout = 120, onExit, failPatterns|
		^super.newCopyArgs(argv, environment, logPath, timeout, onExit, failPatterns ? []).prRun
	}

	*quotePosix { |string| ^string.asString.shellQuote }

	*quoteWindows { |string| ^"\"" ++ string.asString.replace("\"", "\\\"") ++ "\"" }

	*commandLine { |argv, environment, logPath|
		var pairs = environment.keys.asArray.sort.collect { |key| [key.asString, environment[key].asString] };
		^if(thisProcess.platform.name == \windows) {
			// Unverified on Windows: set the isolated variables, then run the program.
			pairs.collect { |pair| "set " ++ this.quoteWindows(pair[0] ++ "=" ++ pair[1]) ++ " && " }.join
			++ argv.collect { |item| this.quoteWindows(item) }.join(" ")
			++ " < NUL > " ++ this.quoteWindows(logPath) ++ " 2>&1"
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
		if(thisProcess.platform.name == \windows) {
			env.putAll((
				USERPROFILE: home,
				APPDATA: home +/+ "AppData/Roaming",
				LOCALAPPDATA: home +/+ "AppData/Local",
				TEMP: tmp,
				TMP: tmp,
				SystemRoot: "SystemRoot".getenv ? "C:\\Windows"
			));
		} {
			env[\PATH] = "/usr/bin:/bin:/usr/sbin:/sbin";
		};
		^env
	}

	prRun {
		var command = MBRenderProcess.commandLine(argv, environment, logPath), checkCounter = 0;
		File.mkdir(logPath.dirname);
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
		if(finished.not and: { pid.notNil } and: { pid > 0 }) {
			thisProcess.platform.killProcessByID(pid);
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
			poller !? { poller.stop };
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

	*analyze { |path, expected, onDone, silenceThresholdDb = -60, clipThreshold = 0.999|
		var routine = Routine {
			var file, outcome;
			file = MBWorkflowTry.value({ SoundFile.openRead(path) });
			if(file.isKindOf(SoundFile).not) {
				onDone.value(MBError(\render, "the rendered file could not be opened as audio: " ++ path.basename));
			} {
				outcome = this.prScan(file, expected, silenceThresholdDb, clipThreshold);
				file.close;
				onDone.value(outcome);
			};
		};
		routine.play(AppClock);
		^routine
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
