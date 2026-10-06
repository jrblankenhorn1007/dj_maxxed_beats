(
// Writes the NRT score for tests/test_chaososc_rate_nrt.py: one Synth whose
// output channels compare ChaosOsc's default rate, explicit rates, the .kr
// constructor, and mul/add. Channel order must match RATE_CHANNELS in the
// Python test. Errors exit non-zero instead of leaving sclang running.
var exitCode = 1;
try {
    var scorePath = thisProcess.nowExecutingPath.dirname +/+ ".build"
        +/+ "chaososc_rate_nrt.osc";
    var probeAr = ChaosOsc.ar;
    var probeKr = ChaosOsc.kr;
    var probeUnity = ChaosOsc.ar(3.9, 0.37, inf, 1.0, 0.0);
    var probeScaled = ChaosOsc.ar(3.9, 0.37, mul: 0.25, add: 0.5);
    var synthDef = SynthDef(\chaosOscRateNrt, { |holdFreq = 100|
        Out.ar(0, [
            ChaosOsc.ar(3.9, 0.37),
            ChaosOsc.ar(3.9, 0.37, inf, 1.0, 0.0),
            ChaosOsc.ar(3.9, 0.37, 48000),
            ChaosOsc.multiNew('audio', 3.9, 0.37),
            ChaosOsc.ar(3.9, 0.37, 100),
            ChaosOsc.ar(3.9, 0.37, holdFreq),
            ChaosOsc.ar(3.9, 0.37, 0),
            K2A.ar(ChaosOsc.kr(3.9, 0.37)),
            K2A.ar(ChaosOsc.kr(3.9, 0.37, 75)),
            ChaosOsc.ar(3.9, 0.37, mul: 0.25, add: 0.5)
        ]);
    });
    var events = [
        [0.0, [\d_recv, synthDef.asBytes]],
        [0.01, [\s_new, \chaosOscRateNrt, 1000, 0, 0, \holdFreq, 100]],
        [0.5, [\n_set, 1000, \holdFreq, 0]],
        [1.0, [\c_set, 0, 0]]
    ];

    ("CHAOSOSC_AR_DEFAULT: " ++ probeAr.class.name ++ " " ++ probeAr.rate
        ++ " " ++ probeAr.inputs.asCompileString).postln;
    ("CHAOSOSC_KR_DEFAULT: " ++ probeKr.class.name ++ " " ++ probeKr.rate
        ++ " " ++ probeKr.inputs.asCompileString).postln;
    ("CHAOSOSC_UNITY_MADD: " ++ probeUnity.class.name).postln;
    ("CHAOSOSC_SCALED_MADD: " ++ probeScaled.class.name ++ " "
        ++ probeScaled.inputs[1..].asCompileString).postln;

    Score(events).writeOSCFile(scorePath);
    "CHAOSOSC_RATE_NRT_SCORE_WRITTEN".postln;
    exitCode = 0;
} { |error|
    error.reportError;
    "CHAOSOSC_RATE_NRT_SCORE_FAILED".postln;
};
exitCode.exit;
)
