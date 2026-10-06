// Real-time ChaosOsc audition driven by tests/test_chaososc_realtime.py (opt-in
// via DJMB_REALTIME_AUDIO_TESTS=1; configured through DJMB_RT_* variables).
//
// Boots a real-time scsynth on the given output-only CoreAudio device (named
// for both directions so the 3.14.1 driver never starts the default input
// device/microphone) at its current sample rate, bound to 127.0.0.1 on the
// given UDP port with no input channels. ChaosOsc renders only to private
// audio buses; RecordBuf captures them, plus the hardware output buses (to
// prove they stay exactly silent), into a float WAV.
//
// Progress and server health are printed as machine-parseable
// "DJMB_RT <EVENT> key=value ..." lines; any failure prints "DJMB_RT FAIL",
// kills the server, and exits sclang with status 1.
(
var setting = { |name, default|
    var value = name.getenv;
    if(value.isNil or: { value.isEmpty }) { default } { value }
};
var port = setting.("DJMB_RT_PORT", "0").asInteger;
var deviceName = setting.("DJMB_RT_DEVICE", "");
var scsynthPath = setting.("DJMB_RT_SCSYNTH", "");
var pluginPaths = setting.("DJMB_RT_PLUGIN_PATHS", "").split($:).reject(_.isEmpty);
var capturePath = setting.("DJMB_RT_CAPTURE_PATH", "");
var captureSeconds = setting.("DJMB_RT_CAPTURE_SECONDS", "2.0").asFloat;
var twinSetSeconds = setting.("DJMB_RT_TWIN_SET_SECONDS", "1.0").asFloat;
var workloadSize = setting.("DJMB_RT_WORKLOAD_SYNTHS", "64").asInteger;
var bootTimeout = setting.("DJMB_RT_BOOT_TIMEOUT_SECONDS", "30").asFloat;
var watchdogSeconds = setting.("DJMB_RT_WATCHDOG_SECONDS", "75").asFloat;
// scsynth's peakCPU is the worst audio callback of roughly the last second,
// so transients must age out before the live workload is measured.
var settleSeconds = setting.("DJMB_RT_SETTLE_SECONDS", "1.5").asFloat;
var changeInterval = 0.25;
var numOutputs = 2;
var finished = false;
var startedAt = Main.elapsedTime;
var server;
var statusReplies = 0, serverFailures = 0, maxNumSynths = 0, maxNumUGens = 0;
// CPU statistics per measurement window: \boot, \warmup, \live, then \quit.
var cpuWindow = \boot, cpuStats = IdentityDictionary.new;
var cpuStat = { |window, key| (cpuStats[window] ? ())[key] ? -1 };
var report, fail, check, await, awaitStatus;

report = { |event ... pairs|
    var line = "DJMB_RT " ++ event;
    pairs.pairsDo { |key, value| line = line ++ " " ++ key ++ "=" ++ value };
    line.postln;
};

fail = { |reason|
    if(finished.not) {
        finished = true;
        ("DJMB_RT FAIL " ++ reason).postln;
        if(server.notNil) {
            server.addr.sendMsg("/quit");
            if(server.pid.notNil) { thisProcess.platform.killProcessByID(server.pid) };
        };
        SystemClock.sched(1.0, { 1.exit; nil });
    };
};

check = { |condition, reason|
    if(condition.not) { Error(reason).throw };
};

// Polls inside the audition Routine; never blocks past `seconds`.
await = { |test, seconds, description|
    var deadline = Main.elapsedTime + seconds;
    while { test.value.not and: { Main.elapsedTime < deadline } } { 0.02.wait };
    check.(test.value, "timed out after % s waiting for %".format(seconds, description));
};

awaitStatus = { |phase|
    var before;
    server.sync;
    before = statusReplies;
    server.sendStatusMsg;
    await.({ statusReplies > before }, 3, "a /status.reply in phase " ++ phase);
    report.("STATUS",
        \phase, phase,
        \serverRunning, server.serverRunning,
        \avgCPU, server.avgCPU,
        \peakCPU, server.peakCPU,
        \numSynths, server.numSynths,
        \numUGens, server.numUGens,
        \numGroups, server.numGroups,
        \numSynthDefs, server.numSynthDefs,
        \sampleRate, server.sampleRate,
        \actualSampleRate, server.actualSampleRate
    );
};

SystemClock.sched(watchdogSeconds, {
    fail.("watchdog expired after % s".format(watchdogSeconds));
    nil
});

fork {
    try {
        var options, booted = false, pidSeen = false, poller;
        var refBus, twinBus, mixBus, warmupBuffer, buffer;
        var startVoices, freeVoices, warmup, voices, stepCount, twinStep, captureStartedAt;
        var quitAcknowledged = false, quitFinished = false;

        check.(port > 0, "DJMB_RT_PORT must be a UDP port number");
        check.(deviceName.notEmpty, "DJMB_RT_DEVICE must name an output-only audio device");
        check.(File.exists(scsynthPath), "DJMB_RT_SCSYNTH does not exist: " ++ scsynthPath);
        check.(pluginPaths.notEmpty, "DJMB_RT_PLUGIN_PATHS is empty");
        check.(capturePath.notEmpty, "DJMB_RT_CAPTURE_PATH is empty");

        Server.program = "exec %".format(scsynthPath.shellQuote);
        options = ServerOptions.new;
        options.device = deviceName;
        options.numInputBusChannels = 0;
        options.numOutputBusChannels = numOutputs;
        options.bindAddress = "127.0.0.1";
        options.ugenPluginsPath = pluginPaths;
        options.loadDefs = false;
        server = Server(\djmbChaosOscRealtime, NetAddr("127.0.0.1", port), options);
        Server.default = server;

        OSCFunc({ |msg|
            var stats = cpuStats[cpuWindow];
            if(stats.isNil) {
                stats = (replies: 0, maxAvgCPU: 0, maxPeakCPU: 0);
                cpuStats[cpuWindow] = stats;
            };
            statusReplies = statusReplies + 1;
            maxNumUGens = max(maxNumUGens, msg[2]);
            maxNumSynths = max(maxNumSynths, msg[3]);
            stats[\replies] = stats[\replies] + 1;
            stats[\maxAvgCPU] = max(stats[\maxAvgCPU], msg[6]);
            stats[\maxPeakCPU] = max(stats[\maxPeakCPU], msg[7]);
            report.("CPU_SAMPLE",
                \window, cpuWindow,
                \t, (Main.elapsedTime - startedAt).round(0.001),
                \avgCPU, msg[6].round(0.001),
                \peakCPU, msg[7].round(0.001),
                \numSynths, msg[3],
                \numUGens, msg[2]
            );
        }, '/status.reply', server.addr);
        OSCFunc({ |msg|
            serverFailures = serverFailures + 1;
            report.("SERVER_FAIL", \message, msg.collect(_.asString).join("|"));
        }, '/fail', server.addr);

        report.("BOOTING", \port, port, \inputs, 0, \outputs, numOutputs,
            \pluginDirs, pluginPaths.size);
        server.waitForBoot({ booted = true });
        await.({
            pidSeen = pidSeen or: { server.pid.notNil };
            check.((pidSeen and: { server.pid.isNil }).not,
                "scsynth exited while booting (see its output above)");
            booted
        }, bootTimeout, "the real-time server to boot (a hang after the "
            "SC_AudioDriver line usually means macOS is waiting on audio-device or "
            "microphone permission)");
        report.("BOOTED",
            \serverRunning, server.serverRunning,
            \pid, server.pid,
            \port, port,
            \sampleRate, server.sampleRate,
            \actualSampleRate, server.actualSampleRate,
            \latency, server.latency
        );
        poller = fork { loop { server.sendStatusMsg; 0.25.wait } };

        refBus = Bus.audio(server, 1);
        twinBus = Bus.audio(server, 1);
        mixBus = Bus.audio(server, 1);
        [refBus, twinBus, mixBus].do { |bus|
            check.(bus.index >= options.firstPrivateBus, "bus % is not private".format(bus));
        };
        SynthDef(\djmbChaosOscRtReference, {
            Out.ar(refBus.index, ChaosOsc.ar(3.9, 0.37));
        }).send(server);
        SynthDef(\djmbChaosOscRtVoice, { |chaosAmount = 3.9, seed = 0.37, amp = 1|
            // never write to hardware outputs, even with a bad \out argument
            var out = \out.kr(mixBus.index).max(options.firstPrivateBus);
            Out.ar(out, ChaosOsc.ar(chaosAmount, seed) * amp);
        }).send(server);
        SynthDef(\djmbChaosOscRtRecorder, { |buf|
            var captured = [In.ar(refBus.index), In.ar(twinBus.index), In.ar(mixBus.index)]
                ++ In.ar(0, numOutputs);
            RecordBuf.ar(captured, buf, loop: 0, doneAction: Done.freeSelf);
        }).send(server);
        buffer = Buffer.alloc(server, (captureSeconds * server.sampleRate).round.asInteger,
            3 + numOutputs);
        warmupBuffer = Buffer.alloc(server, 16 * options.blockSize, 3 + numOutputs);
        server.sync;

        // Starts the reference ChaosOsc.ar(3.9, 0.37), its twin (same values
        // through controls), the workload, and the recorder in one bundle, so
        // they share a first block; the recorder frees itself when full.
        startVoices = { |recordBuffer|
            var started = (ended: false);
            server.makeBundle(server.latency, {
                started[\reference] = Synth(\djmbChaosOscRtReference, nil,
                    server.defaultGroup, \addToTail);
                started[\twin] = Synth(\djmbChaosOscRtVoice,
                    [\out, twinBus.index, \chaosAmount, 3.9, \seed, 0.37, \amp, 1],
                    server.defaultGroup, \addToTail);
                started[\workload] = Array.fill(workloadSize, {
                    Synth(\djmbChaosOscRtVoice, [
                        \out, mixBus.index,
                        \chaosAmount, rrand(3.4, 4.2),
                        \seed, rrand(0.05, 0.95),
                        \amp, workloadSize.reciprocal
                    ], server.defaultGroup, \addToTail)
                });
                started[\recorder] = Synth(\djmbChaosOscRtRecorder,
                    [\buf, recordBuffer.bufnum], RootNode(server), \addToTail);
            });
            OSCFunc({
                started[\endedAt] = Main.elapsedTime;
                started[\ended] = true;
            }, '/n_end', server.addr, argTemplate: [started[\recorder].nodeID]).oneShot;
            started
        };
        freeVoices = { |started|
            (started[\workload] ++ [started[\reference], started[\twin]]).do(_.free);
        };

        // The first instantiation of a SynthDef costs scsynth a one-off CPU
        // transient (built-in UGens included), so instantiate everything once,
        // report that separately, and let it age out of peakCPU.
        cpuWindow = \warmup;
        thisThread.randSeed = 1;
        warmup = startVoices.(warmupBuffer);
        await.({ warmup[\ended] }, 5, "the warm-up recorder to finish");
        freeVoices.(warmup);
        server.sync;
        warmupBuffer.free;
        settleSeconds.wait;

        cpuWindow = \live;
        thisThread.randSeed = 20261006;
        captureStartedAt = Main.elapsedTime;
        voices = startVoices.(buffer);
        // Live control changes, timestamped relative to the start bundle; some
        // values are deliberately outside ChaosOsc's clamped [3.57, 3.999].
        stepCount = (captureSeconds / changeInterval).round.asInteger;
        twinStep = (twinSetSeconds / changeInterval).round.asInteger;
        stepCount.do { |index|
            var step = index + 1;
            changeInterval.wait;
            server.makeBundle(server.latency, {
                voices[\workload].do { |synth| synth.set(\chaosAmount, rrand(3.4, 4.2)) };
                if(step == twinStep) { voices[\twin].set(\chaosAmount, 3.7) };
            });
        };
        await.({ voices[\ended] }, captureSeconds + 5, "the RecordBuf capture to finish");
        awaitStatus.(\workload);
        voices[\workload].do(_.free);
        awaitStatus.(\workloadFreed);
        [voices[\reference], voices[\twin]].do(_.free);
        awaitStatus.(\allFreed);

        buffer.write(capturePath, "wav", "float");
        server.sync;
        check.(File.exists(capturePath), "Buffer.write did not create " ++ capturePath);
        report.("CAPTURE",
            \frames, buffer.numFrames,
            \channels, buffer.numChannels,
            \sampleRate, server.sampleRate,
            \captureWallSeconds, voices[\endedAt] - captureStartedAt,
            \twinSetSeconds, twinStep * changeInterval,
            \workloadSynths, workloadSize
        );
        buffer.free;
        server.sync;
        poller.stop;
        cpuWindow = \quit;
        report.("CPU",
            \statusReplies, statusReplies,
            \bootReplies, cpuStat.(\boot, \replies),
            \bootMaxPeakCPU, cpuStat.(\boot, \maxPeakCPU),
            \warmupReplies, cpuStat.(\warmup, \replies),
            \warmupMaxPeakCPU, cpuStat.(\warmup, \maxPeakCPU),
            \liveReplies, cpuStat.(\live, \replies),
            \liveMaxAvgCPU, cpuStat.(\live, \maxAvgCPU),
            \liveMaxPeakCPU, cpuStat.(\live, \maxPeakCPU),
            \maxNumSynths, maxNumSynths,
            \maxNumUGens, maxNumUGens,
            \serverFailures, serverFailures,
            \avgCPU, server.avgCPU,
            \peakCPU, server.peakCPU
        );

        server.quit({ quitAcknowledged = true; quitFinished = true }, { quitFinished = true });
        await.({ quitFinished }, 10, "the server to acknowledge /quit");
        await.({ server.pid.isNil }, 10, "the scsynth process to exit");
        report.("QUIT",
            \quitAcknowledged, quitAcknowledged,
            \serverProcessExited, server.pid.isNil
        );
        check.(quitAcknowledged, "the server did not acknowledge /quit");
        finished = true;
        report.("DONE");
        0.exit;
    } { |error|
        fail.(error.errorString.replace("\n", " "));
    };
};
)
