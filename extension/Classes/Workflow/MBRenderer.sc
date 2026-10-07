/*
Approved offline rendering of a project composition.

MBRenderer.render(project, entryPath, settings, approved, onProgress,
onSuccess, onFailure) refuses unless approved === true. It then runs the
entry .scd in a separate headless sclang process (isolated HOME and minimal
environment, include paths for the MaxxedBeats and ChaosOsc classes) to
build a Score, renders it with scsynth -N (ChaosOsc plugin path from the
installed Extensions by default), checks the result, and writes a unique
<project>/renders/<name>-<stamp>.wav plus a .json metadata sidecar.
Generated code never runs in the calling interpreter. Returns a handle that
responds to .cancel. See docs/design/workflow.md for settings.
*/
MBRenderer {
	classvar <>defaultSclang, <>defaultScsynth, <>defaultPluginPaths, <>defaultBuiltinPluginPaths;
	classvar <>defaultTimeout = 120, <>maxTimeout = 3600;
	classvar <sampleFormats = #["float", "int24", "int16"];
	classvar <metadataKeys = #[\summary, \prompt, \provider, \model, \candidate, \sessionId, \plan];
	classvar counter = 0;

	var project, entryPath, entryAbsolute, settings, onProgress, onSuccess, onFailure, handle;
	var sclang, scsynth, includePaths, pluginPaths, timeout, workDir, scorePath, outputPath, metadataPath;
	var process, analysis, droppedEvents = 0, startedAt;

	*render { |project, entryPath, settings, approved = false, onProgress, onSuccess, onFailure|
		^super.new.prStart(project, entryPath, settings, approved, onProgress, onSuccess, onFailure)
	}

	*platformSclang {
		^defaultSclang ?? {
			case
			{ thisProcess.platform.name == \osx } { Platform.resourceDir.dirname +/+ "MacOS/sclang" }
			{ thisProcess.platform.name == \windows } { Platform.resourceDir +/+ "sclang.exe" }
			{ this.which("sclang") }
		}
	}

	*platformScsynth {
		^defaultScsynth ?? {
			case
			{ thisProcess.platform.name == \osx } { Platform.resourceDir +/+ "scsynth" }
			{ thisProcess.platform.name == \windows } { Platform.resourceDir +/+ "scsynth.exe" }
			{ this.which("scsynth") }
		}
	}

	*which { |name|
		["/usr/local/bin", "/usr/bin", "/opt/homebrew/bin"].do { |dir|
			if(File.exists(dir +/+ name)) { ^dir +/+ name }
		};
		^name
	}

	*builtinPluginPaths {
		^defaultBuiltinPluginPaths ?? {
			[
				Platform.resourceDir +/+ "plugins",
				"/usr/local/lib/SuperCollider/plugins",
				"/usr/lib/SuperCollider/plugins"
			].select { |dir| File.exists(dir) }.keep(1)
		}
	}

	// The Extensions folders plus the folder of the installed ChaosOsc
	// language class when it holds the ChaosOsc plugin binary.
	*extensionPluginPaths {
		^defaultPluginPaths ?? {
			([Platform.userExtensionDir, Platform.systemExtensionDir] ++ this.chaosOscPluginDirs)
				.select { |dir| dir.notNil and: { File.exists(dir) } }
		}
	}

	*chaosOscPluginDirs {
		var chaos = \ChaosOsc.asClass, classDir, folder;
		if(chaos.isNil) { ^[] };
		classDir = chaos.filenameSymbol.asString.dirname;
		folder = classDir.dirname;
		^[folder, classDir].select { |dir|
			["ChaosOsc.scx", "ChaosOsc.so"].any { |name| File.exists(dir +/+ name) }
		}.keep(1)
	}

	*classIncludePaths {
		var quarkClasses = this.filenameSymbol.asString.dirname.dirname, chaos = \ChaosOsc.asClass, paths;
		if(chaos.isNil) {
			MBError(\config, "the ChaosOsc language class is not installed; install MaxxedBeats with its ChaosOsc plugin").throw
		};
		paths = [quarkClasses, chaos.filenameSymbol.asString.dirname];
		^this.uniqueDirs(paths)
	}

	// Real, existing, de-duplicated directories; nested duplicates are dropped.
	// Comparisons are separator-agnostic (and case-insensitive on Windows).
	*uniqueDirs { |dirs|
		var real = dirs.collect { |dir| File.realpath(dir.asString.standardizePath) }.reject(_.isNil)
			.collect(_.withoutTrailingSlash);
		var result = List.new, same, inside;
		same = { |a, b| MBProject.comparablePath(a) == MBProject.comparablePath(b) };
		inside = { |a, b| MBProject.comparablePath(a).beginsWith(MBProject.comparablePath(b) ++ "/") };
		real.do { |dir|
			if(result.any { |kept| same.(kept, dir) or: { inside.(dir, kept) } }.not) {
				result = result.reject { |kept| inside.(kept, dir) };
				result.add(dir);
			}
		};
		^result.asArray
	}

	// Windows: the class library folder next to the given sclang.exe.
	*classLibraryFor { |sclangPath|
		^sclangPath.asString.dirname +/+ "SCClassLibrary"
	}

	// Windows: a YAML string literal (single quotes; quotes doubled).
	*yamlString { |text| ^"'" ++ text.asString.replace("'", "''") ++ "'" }

	*fail { |kind, detail| MBError(kind, detail).throw }

	*sanitizeName { |name|
		var clean = name.asString.collect { |char| if(char.isAlphaNum or: { char == $- } or: { char == $_ }) { char } { $- } };
		clean = clean.keep(48);
		^if(clean.isEmpty) { "render" } { clean }
	}

	prStart { |argProject, argEntry, rawSettings, approved, argProgress, argSuccess, argFailure|
		var prepared;
		project = argProject;
		entryPath = argEntry;
		onProgress = argProgress;
		onSuccess = argSuccess;
		onFailure = argFailure;
		handle = MBWorkflowHandle.new;
		if(approved !== true) {
			this.prFail(MBError(\validation, "the render was not started: approve this render (composition, "
				++ "settings, and output folder) first"));
			^handle
		};
		handle.onCancel {
			process !? { process.cancel };
			analysis !? { analysis.stop };
			this.prRemoveOutputs;
			AppClock.sched(0, { onFailure.value(MBError(\cancelled, "the render was cancelled")); nil });
		};
		prepared = MBWorkflowTry.mbError({ this.prPrepare(rawSettings ? ()) }, \render);
		if(prepared.isKindOf(MBError)) {
			this.prRemoveOutputs;
			this.prFail(prepared);
			^handle
		};
		startedAt = Main.elapsedTime;
		this.prBuildScore;
		^handle
	}

	prPrepare { |raw|
		var base, stamp, name, seed, format, extra, sidecar;
		if(project.respondsTo(\resolveEditable).not) { MBRenderer.fail(\validation, "render needs an MBProject") };
		entryAbsolute = project.resolveEditable(entryPath);
		if(entryPath.asString.toLower.endsWith(".scd").not) {
			MBRenderer.fail(\validation, "only .scd compositions can be rendered: " ++ entryPath.asString.quote)
		};
		if(File.exists(entryAbsolute).not) {
			MBRenderer.fail(\io, "the composition does not exist in the project: " ++ entryPath.asString.quote)
		};
		if(raw.isKindOf(Dictionary).not) { MBRenderer.fail(\validation, "render settings must be an Event") };
		settings = MBResponseFormat.renderSettings(raw, false);
		seed = raw[\seed] ? 0.5;
		settings[\seed] = MBResponseFormat.seedValue(seed);
		format = (raw[\sampleFormat] ? "float").asString;
		if(sampleFormats.includesEqual(format).not) {
			MBRenderer.fail(\validation, "sampleFormat must be one of " ++ sampleFormats.join(", "))
		};
		settings[\sampleFormat] = format;
		settings[\silenceThresholdDb] = raw[\silenceThresholdDb] ? -60;
		settings[\clipThreshold] = raw[\clipThreshold] ? 0.999;
		timeout = raw[\timeout] ? defaultTimeout;
		if(timeout.isKindOf(SimpleNumber).not or: { timeout <= 0 } or: { timeout > maxTimeout }) {
			MBRenderer.fail(\validation, "timeout must be between 0 and " ++ maxTimeout ++ " seconds")
		};
		settings[\timeout] = timeout;
		extra = raw[\metadata] ? ();
		settings[\metadata] = ();
		metadataKeys.do { |key|
			extra[key] !? { |value| settings[\metadata][key] = MBResponseFormat.redact(value.asString).keep(2000) }
		};

		sclang = (raw[\sclang] ? MBRenderer.platformSclang).asString;
		scsynth = (raw[\scsynth] ? MBRenderer.platformScsynth).asString;
		[[sclang, "sclang", "defaultSclang"], [scsynth, "scsynth", "defaultScsynth"]].do { |triple|
			if(File.exists(triple[0]).not) {
				MBRenderer.fail(\config, triple[1] ++ " was not found at " ++ triple[0].quote
					++ "; set the " ++ triple[1] ++ " render setting or MBRenderer." ++ triple[2])
			}
		};
		includePaths = MBRenderer.uniqueDirs(MBRenderer.classIncludePaths ++ (raw[\includePaths] ? []));
		if(MBRenderProcess.isWindows and: { File.exists(MBRenderer.classLibraryFor(sclang)).not }) {
			MBRenderer.fail(\config, "the SuperCollider class library was not found next to " ++ sclang.quote
				++ "; set the sclang render setting to the sclang.exe of a complete SuperCollider installation")
		};
		pluginPaths = (raw[\builtinPluginPaths] ? MBRenderer.builtinPluginPaths)
			++ (raw[\pluginPaths] ? MBRenderer.extensionPluginPaths);
		if(pluginPaths.any { |dir| File.exists(dir.asString).not }) {
			MBRenderer.fail(\config, "a plugin folder does not exist: "
				++ pluginPaths.detect { |dir| File.exists(dir.asString).not }.asString.quote)
		};
		pluginPaths = MBRenderer.uniqueDirs(pluginPaths);
		if(pluginPaths.isEmpty) { MBRenderer.fail(\config, "no scsynth plugin folders were found; set builtinPluginPaths") };

		counter = counter + 1;
		stamp = Date.getDate.format("%Y%m%d-%H%M%S");
		workDir = project.dataDir +/+ "renders" +/+ (stamp ++ "-" ++ counter.asStringToBase(10, 3)
			++ "-" ++ 1000000.rand.asStringToBase(10, 6));
		File.mkdir(workDir +/+ "home");
		File.mkdir(workDir +/+ "tmp");
		scorePath = workDir +/+ "score.osc";
		if(MBRenderProcess.isWindows) { this.prWriteWindowsConfig };

		base = MBRenderer.sanitizeName(raw[\name] ? entryPath.asString.basename.splitext[0]);
		File.mkdir(project.rendersDir);
		name = base ++ "-" ++ stamp;
		sidecar = 1;
		while { File.exists(project.rendersDir +/+ name ++ ".wav") or: { File.exists(project.rendersDir +/+ name ++ ".json") } } {
			sidecar = sidecar + 1;
			name = base ++ "-" ++ stamp ++ "-" ++ sidecar;
		};
		outputPath = project.rendersDir +/+ name ++ ".wav";
		metadataPath = project.rendersDir +/+ name ++ ".json";
		// Reserve the name immediately so concurrent renders never collide.
		MBProject.writeFile(metadataPath, MBWorkflowJSON.stringify((format: "maxxedbeats.render/1", status: "rendering")));
		MBProject.writeFile(workDir +/+ "entry-snapshot.scd", MBProject.readFile(entryAbsolute));
		MBProject.writeFile(workDir +/+ "runner.scd", this.prRunnerSource);
	}

	prRunnerSource {
		var values = (duration: settings[\duration], sampleRate: settings[\sampleRate],
			numChannels: settings[\numChannels], seed: settings[\seed]);
		^"// Generated by MBRenderer; runs only in a separate headless sclang process.\n(\n"
		++ "var settings = " ++ values.asCompileString ++ ";\n"
		++ "var entryPath = " ++ entryAbsolute.asCompileString ++ ";\n"
		++ "var scorePath = " ++ scorePath.asCompileString ++ ";\n"
		++ "var seedInt = " ++ (settings[\seed] * 2147483646).asInteger ++ ";\n"
		++ "var outcome, events, kept, dropped = 0, problem, written;\n"
		++ "~mbRender = settings.copy;\n"
		++ "outcome = MBWorkflowTry.value({ thisThread.randSeed = seedInt; thisProcess.interpreter.executeFile(entryPath) });\n"
		++ "case\n"
		++ "    { outcome.isKindOf(Error) } { outcome.reportError; problem = \"the composition raised an error: \" ++ outcome.errorString }\n"
		++ "    { outcome.isNil } { problem = \"the composition returned nothing; it may contain a syntax error (see the ERROR lines above)\" }\n"
		++ "    { outcome.isKindOf(Score) } { events = outcome.score }\n"
		++ "    { outcome.isKindOf(SequenceableCollection) and: { outcome.isString.not } } { events = outcome };\n"
		++ "if(problem.isNil and: { events.isNil or: { events.every { |event| event.isKindOf(SequenceableCollection) and: { event.isString.not } and: { event.size >= 2 } and: { event[0].isKindOf(SimpleNumber) } and: { event[0] >= 0 } and: { event[0] < inf } }.not } }) {\n"
		++ "    problem = \"the composition must return a Score (or an Array of [time, OSC message] events) as its last expression; got \" ++ outcome.class.name\n"
		++ "};\n"
		++ "if(problem.isNil) {\n"
		++ "    kept = events.select { |event| if(event[0] < settings[\\duration]) { true } { dropped = dropped + 1; false } };\n"
		++ "    // scsynth -N renders through the block that contains the last command.\n"
		++ "    kept = kept.add([settings[\\duration] - (1 / settings[\\sampleRate]), [\\c_set, 0, 0]]);\n"
		++ "    written = MBWorkflowTry.value({ Score(kept).sort.writeOSCFile(scorePath); nil });\n"
		++ "    if(written.isKindOf(Error)) { problem = \"the Score could not be written: \" ++ written.errorString };\n"
		++ "};\n"
		++ "if(problem.isNil) {\n"
		++ "    (\"MB_RENDER_SCORE_WRITTEN events=\" ++ kept.size ++ \" dropped=\" ++ dropped).postln;\n"
		++ "    0.exit;\n"
		++ "} {\n"
		++ "    (\"MB_RENDER_ERROR: \" ++ problem).postln;\n"
		++ "    1.exit;\n"
		++ "};\n"
		++ ")\n"
	}

	// Windows: sclang finds the user's folders with SHGetKnownFolderPath, not
	// environment variables, so the child gets an explicit configuration:
	// `-l sclang_conf.yaml` with excludeDefaultPaths (no user or system
	// Extensions, no Quarks) and explicit include paths, plus a generated
	// class extension that points its user folders into the isolated home
	// and skips the user's startup files.
	prWriteWindowsConfig {
		var isolation = workDir +/+ "isolation", appSupport = workDir +/+ "home" +/+ "AppData" +/+ "Local" +/+ "SuperCollider";
		var paths = [MBRenderer.classLibraryFor(sclang)] ++ includePaths ++ [isolation];
		File.mkdir(isolation);
		File.mkdir(appSupport);
		MBProject.writeFile(isolation +/+ "MBRenderIsolation.sc",
			"// Generated by MBRenderer for one isolated render child process only.\n"
			++ "+ Platform {\n"
			++ "\tuserAppSupportDir { ^" ++ appSupport.asCompileString ++ " }\n"
			++ "\tuserConfigDir { ^" ++ appSupport.asCompileString ++ " }\n"
			++ "\tuserExtensionDir { ^" ++ (appSupport +/+ "Extensions").asCompileString ++ " }\n"
			++ "\tloadStartupFiles { }\n"
			++ "}\n");
		MBProject.writeFile(workDir +/+ "sclang_conf.yaml",
			"includePaths:\n" ++ paths.collect { |path| "    - " ++ MBRenderer.yamlString(path) ++ "\n" }.join
			++ "excludePaths: []\npostInlineWarnings: false\nexcludeDefaultPaths: true\n");
	}

	prEnvironment {
		^MBRenderProcess.isolatedEnvironment(workDir +/+ "home", workDir +/+ "tmp")
	}

	prProgress { |stage, fraction, message|
		if(handle.active) {
			AppClock.sched(0, { onProgress.value((stage: stage, fraction: fraction, message: message)); nil });
		};
	}

	prBuildScore {
		var argv = if(MBRenderProcess.isWindows) {
			[sclang, "-l", workDir +/+ "sclang_conf.yaml", workDir +/+ "runner.scd"]
		} {
			[sclang] ++ includePaths.collect { |dir| ["--include-path", dir] }.flatten ++ [workDir +/+ "runner.scd"]
		};
		this.prProgress(\building, 0.05, "Building the Score from " ++ entryPath.asString ++ " in a separate sclang process");
		process = MBRenderProcess.run(argv, this.prEnvironment, workDir +/+ "sclang.log", timeout, { |finished|
			// After a cancel, clean again once the child has really exited:
			// a dying child can recreate files in its isolated HOME.
			if(handle.active) { this.prScoreBuilt(finished) } { this.prCleanHome };
		}, ["Library has not been compiled successfully", "ERROR: duplicate Class"]);
	}

	prLogHint { |name| ^".maxxedbeats/renders/" ++ workDir.basename +/+ name }

	prFailureDetail { |log|
		var lines = log.split($\n), marker, errorIndex, excerpt;
		marker = lines.detect { |line| line.beginsWith("MB_RENDER_ERROR: ") };
		errorIndex = lines.detectIndex { |line| line.beginsWith("ERROR:") or: { line.beginsWith("FAILURE IN SERVER") } };
		excerpt = errorIndex !? { lines.copyRange(errorIndex, min(errorIndex + 2, lines.size - 1)).join(" ").stripWhiteSpace };
		^MBResponseFormat.redact(
			if(marker.notNil) {
				marker.copyRange(17, marker.size - 1) ++ (excerpt !? { |text| if(marker.contains(text.keep(40))) { "" } { " (" ++ text ++ ")" } } ? "")
			} {
				excerpt ? "no error message was printed"
			}
		).keep(800)
	}

	prScoreBuilt { |finished|
		var log = MBRenderProcess.readLog(finished.logPath), detail, dropped;
		case
		{ finished.cancelled } { nil }
		{ finished.timedOut } {
			this.prFailAndClean(MBError(\render, "building the Score timed out after " ++ timeout
				++ " seconds; the composition may loop forever or wait on a server. Full log: " ++ this.prLogHint("sclang.log")))
		}
		{ finished.failMatch.notNil } {
			this.prFailAndClean(MBError(\render, "the render process could not compile its class library (" ++ finished.failMatch
				++ "); check that MaxxedBeats and ChaosOsc are each installed once. Full log: " ++ this.prLogHint("sclang.log")))
		}
		{ finished.exitCode != 0 or: { log.contains("MB_RENDER_ERROR: ") } or: { log.contains("MB_RENDER_SCORE_WRITTEN").not }
			or: { File.exists(scorePath).not } } {
			detail = this.prFailureDetail(log);
			this.prFailAndClean(MBError(\render, "building the Score from " ++ entryPath.asString ++ " failed: " ++ detail
				++ ". Fix the composition or ask the DJ for a fix. Full log: " ++ this.prLogHint("sclang.log")))
		}
		{
			dropped = log.findRegexp("dropped=([0-9]+)");
			droppedEvents = if(dropped.size >= 2) { dropped[1][1].asInteger } { 0 };
			this.prRenderAudio;
		};
	}

	prRenderAudio {
		var separator = if(thisProcess.platform.name == \windows) { ";" } { ":" };
		var argv = [scsynth, "-U", pluginPaths.join(separator), "-o", settings[\numChannels].asString,
			"-m", "65536", "-D", "0", "-N", scorePath, "_", outputPath, settings[\sampleRate].asString,
			"WAV", settings[\sampleFormat]];
		this.prProgress(\rendering, 0.4, "Rendering " ++ settings[\duration] ++ " s offline with scsynth (NRT)");
		process = MBRenderProcess.run(argv, this.prEnvironment, workDir +/+ "scsynth.log",
			max(timeout, settings[\duration] * 4), { |finished|
				if(handle.active) { this.prAudioRendered(finished) } { this.prCleanHome };
			});
	}

	prAudioRendered { |finished|
		var log = MBRenderProcess.readLog(finished.logPath), missing;
		missing = log.findRegexp("UGen '([^']+)' not installed");
		case
		{ finished.cancelled } { nil }
		{ finished.timedOut } {
			this.prFailAndClean(MBError(\render, "scsynth timed out while rendering. Full log: " ++ this.prLogHint("scsynth.log")))
		}
		{ missing.size >= 2 } {
			this.prFailAndClean(MBError(\render, "scsynth could not load the " ++ missing[1][1] ++ " UGen plugin. Install "
				++ "the ChaosOsc plugin with the MaxxedBeats installer (or set pluginPaths to the folder that contains it). "
				++ "Full log: " ++ this.prLogHint("scsynth.log")))
		}
		{ finished.exitCode != 0 or: { File.exists(outputPath).not } or: { File.fileSize(outputPath) <= 44 } } {
			this.prFailAndClean(MBError(\render, "scsynth failed to render the Score (exit code " ++ finished.exitCode
				++ "): " ++ this.prFailureDetail(log) ++ ". Full log: " ++ this.prLogHint("scsynth.log")))
		}
		{
			this.prProgress(\checking, 0.85, "Checking duration, format, silence, and clipping");
			analysis = MBAudioCheck.analyze(outputPath, settings, { |outcome|
				if(handle.active) { this.prChecked(outcome) };
			}, settings[\silenceThresholdDb], settings[\clipThreshold]);
		};
	}

	prChecked { |outcome|
		var result, metadata, written, warnings = List.new;
		if(outcome.isKindOf(MBError)) { ^this.prFailAndClean(outcome) };
		if(droppedEvents > 0) { warnings.add(droppedEvents.asString ++ " event(s) after the render duration were dropped") };
		if(outcome[\checks][\silent]) { warnings.add("the render is silent (peak below " ++ settings[\silenceThresholdDb] ++ " dBFS)") };
		if(outcome[\checks][\clipped]) { warnings.add("the render clips (" ++ outcome[\checks][\clippedSamples] ++ " samples at full scale)") };
		if(outcome[\checks][\finite].not) { warnings.add("the render contains NaN or infinite samples") };
		if(outcome[\checks][\durationOk].not) { warnings.add("the rendered duration does not match the requested duration") };
		if(outcome[\checks][\formatOk].not) { warnings.add("the rendered format does not match the requested settings") };
		metadata = (
			format: "maxxedbeats.render/1",
			status: "rendered",
			createdAt: Date.getDate.format("%Y-%m-%dT%H:%M:%S"),
			entry: entryPath.asString,
			output: outputPath.basename,
			settings: (duration: settings[\duration], sampleRate: settings[\sampleRate],
				numChannels: settings[\numChannels], sampleFormat: settings[\sampleFormat], seed: settings[\seed]),
			seed: settings[\seed],
			duration: outcome[\duration],
			sampleRate: outcome[\sampleRate],
			numChannels: outcome[\numChannels],
			checks: outcome[\checks],
			warnings: warnings.asArray,
			droppedEvents: droppedEvents,
			renderSeconds: (Main.elapsedTime - startedAt).round(0.01),
			workFolder: ".maxxedbeats/renders/" ++ workDir.basename
		);
		metadata.putAll(settings[\metadata]);
		written = MBWorkflowTry.mbError({ MBProject.writeFile(metadataPath, MBWorkflowJSON.stringify(metadata)) }, \io);
		if(written.isKindOf(MBError)) { ^this.prFailAndClean(written) };
		this.prCleanHome;
		result = (
			path: outputPath,
			metadataPath: metadataPath,
			duration: outcome[\duration],
			sampleRate: outcome[\sampleRate],
			numChannels: outcome[\numChannels],
			sampleFormat: settings[\sampleFormat],
			seed: settings[\seed],
			entry: entryPath.asString,
			checks: outcome[\checks],
			warnings: warnings.asArray,
			workDir: workDir
		);
		this.prProgress(\done, 1.0, "Rendered " ++ outputPath.basename);
		handle.finish;
		AppClock.sched(0, { onSuccess.value(result); nil });
	}

	prCleanHome {
		if(workDir.notNil and: {
			MBProject.comparablePath(workDir).beginsWith(MBProject.comparablePath(project.dataDir) ++ "/")
		}) {
			MBWorkflowTry.value({ File.deleteAll(workDir +/+ "home"); File.deleteAll(workDir +/+ "tmp") });
		};
	}

	prRemoveOutputs {
		[outputPath, metadataPath].do { |path|
			if(path.notNil and: { File.exists(path) }) { File.delete(path) };
		};
		this.prCleanHome;
	}

	prFailAndClean { |error|
		this.prRemoveOutputs;
		this.prFail(error);
	}

	prFail { |error|
		if(handle.active) {
			handle.finish;
			AppClock.sched(0, { onFailure.value(error); nil });
		};
	}
}
