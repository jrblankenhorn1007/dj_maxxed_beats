(
var scorePath = thisProcess.nowExecutingPath.dirname +/+ ".build" +/+ "chaososc_nrt.osc";
var synthDef = SynthDef(\chaosOscNrt, {
    |chaosAmount = 3.9, seed = 0.37, seedCandidate = 0.37, amountCandidate = 3.9|
    var baseline = ChaosOsc.ar(chaosAmount, seed);
    var seedUpdated = ChaosOsc.ar(chaosAmount, seedCandidate);
    var amountUpdated = ChaosOsc.ar(amountCandidate, seed);
    Out.ar(0, [
        baseline * 0.1,
        seedUpdated * 0.1,
        amountUpdated * 0.1
    ]);
});
var events = [
    [0.0, [\d_recv, synthDef.asBytes]],
    [0.01, [
        \s_new, \chaosOscNrt, 1000, 0, 0,
        \chaosAmount, 3.9,
        \seed, 0.37,
        \seedCandidate, 0.37,
        \amountCandidate, 3.9
    ]],
    [0.5, [
        \n_set, 1000,
        \seedCandidate, 0.91,
        \amountCandidate, 3.7
    ]],
    [1.0, [\c_set, 0, 0]]
];

Score(events).writeOSCFile(scorePath);
"CHAOSOSC_NRT_SCORE_WRITTEN".postln;
0.exit;
)
