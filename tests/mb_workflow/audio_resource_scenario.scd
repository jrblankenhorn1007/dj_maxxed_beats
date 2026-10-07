(
var here = thisProcess.nowExecutingPath.dirname, work = thisProcess.argv[0];
(here +/+ "harness.scd").load;
AppClock.sched(60, { "MBTEST FAIL watchdog :: audio resource scenario timed out".postln; 1.exit; nil });
Routine {
	var path = work +/+ "audio.wav", file, operation, captured, called = false, outcome, oldChunk;
	try {
		file = SoundFile.new;
		file.headerFormat = "WAV";
		file.sampleFormat = "float";
		file.numChannels = 1;
		file.sampleRate = 48000;
		file.openWrite(path);
		file.writeData(FloatArray.fill(128, { 0.1 }));
		file.close;
		oldChunk = MBAudioCheck.chunkFrames;
		MBAudioCheck.chunkFrames = 1;
		operation = MBAudioCheck.analyze(path, (duration: 128 / 48000, sampleRate: 48000, numChannels: 1),
			{ called = true });
		0.yield;
		captured = operation.tryPerform(\file);
		~check.("cancel_during_scan_has_open_file", captured.notNil and: { captured.isOpen });
		operation.stop;
		~check.("cancel_closes_file", captured.notNil and: { captured.isOpen.not });
		0.01.wait;
		~check.("cancel_stops_callback", called.not);
		operation.stop;
		operation = MBAudioCheck.analyze(path, (), { called = true });
		operation.stop;
		0.01.wait;
		~check.("stop_before_start_does_not_open",
			called.not and: { operation.tryPerform(\file).isNil });
		MBAudioCheck.chunkFrames = 128;
		outcome = ~await.({ |ok, fail|
			operation = MBAudioCheck.analyze(path, (duration: 128 / 48000, sampleRate: 48000, numChannels: 1), ok)
		});
		~check.("normal_scan_closes_file", outcome[0] == \ok
			and: { outcome[1].isKindOf(Dictionary) }
			and: { outcome[1][\checks][\ok] == true }
			and: { operation.tryPerform(\file).notNil }
			and: { operation.file.isOpen.not }, ~describe.(outcome));
		outcome = ~await.({ |ok, fail| operation = MBAudioCheck.analyze(path, nil, ok) }, 1);
		~check.("error_scan_closes_file", outcome[0] == \ok
			and: { outcome[1].isKindOf(MBError) }
			and: { operation.tryPerform(\file).notNil }
			and: { operation.file.isOpen.not }, ~describe.(outcome));
		MBAudioCheck.chunkFrames = oldChunk;
	} { |error| ~check.("uncaught_error", false, error.errorString) };
	~finish.value;
}.play(AppClock);
)
