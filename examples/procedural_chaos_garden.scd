/*
Procedural Chaos Garden

This is a reviewable, seeded SuperCollider composition built with the
MaxxedBeatsComposition class and the ChaosOsc server UGen. The render helper
passes three arguments: OSC score path, duration in seconds, and seed.

From the repository root, build ChaosOsc once and render without a real-time
server or audio device:
    bash plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh
    python3 scripts/render_composition.py --output chaos-garden.wav

When evaluated in SCIDE without command-line arguments, the Score is stored
in ~maxxedBeatsScore for inspection. Rendering is intentionally handled by the
explicit scsynth NRT command rather than .play or Server.boot.
*/
(
var args, duration, seed, score, scorePath;

args = thisProcess.argv;
duration = if(args.size > 1, { args[1].asFloat }, { 9.0 });
seed = if(args.size > 2, { args[2].asFloat }, { 0.37 });
score = MaxxedBeatsComposition.score(duration, seed);

if(args.size > 0) {
    scorePath = args[0];
    score.writeOSCFile(scorePath);
    "MAXXED_BEATS_COMPOSITION_SCORE_WRITTEN".postln;
    0.exit;
} {
    ~maxxedBeatsScore = score;
    "Procedural Chaos Garden Score stored in ~maxxedBeatsScore.".postln;
    "Render it with: python3 scripts/render_composition.py --output chaos-garden.wav"
        .postln;
};
)
