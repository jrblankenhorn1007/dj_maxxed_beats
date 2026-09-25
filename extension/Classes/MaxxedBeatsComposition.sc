/*
Seeded, file-based procedural composition for the Maxxed Beats extension.
This class builds a SuperCollider NRT Score and never boots a real-time server.
*/
MaxxedBeatsComposition {
    *score { |duration = 9.0, seed = 0.37|
        var totalSeconds, seedValue, scale, stepCount, stepDuration;
        var droneDef, pulseDef, events, rotation;

        totalSeconds = duration.asFloat;
        seedValue = seed.asFloat;

        if(totalSeconds < 4.0) {
            Error("MaxxedBeatsComposition duration must be at least 4 seconds").throw;
        };
        if(seedValue <= 0.0 or: { seedValue >= 1.0 }) {
            Error("MaxxedBeatsComposition seed must be between 0 and 1").throw;
        };

        scale = [0, 3, 5, 7, 10, 12, 10, 7];
        stepCount = 16;
        stepDuration = (totalSeconds - 2.0) / (stepCount - 1);
        rotation = ((seedValue * 13.0).floor.asInteger % scale.size);

        droneDef = SynthDef(\maxxedBeatsDrone, {
            |out = 0, freq = 55, seed = 0.37, amp = 0.1, pan = 0, gate = 1|
            var chaos, carrier, overtone, envelope, signal;

            chaos = ChaosOsc.ar(3.82, seed);
            carrier = SinOsc.ar(freq * (1.0 + (chaos * 0.008)));
            overtone = SinOsc.ar(freq * 2.01);
            envelope = EnvGen.kr(
                Env.asr(0.25, 1.0, 0.45),
                gate,
                doneAction: 2
            );
            signal = (carrier * 0.6) + (overtone * 0.25) + (chaos * 0.15);
            Out.ar(out, Pan2.ar(signal * amp * envelope, pan));
        });

        pulseDef = SynthDef(\maxxedBeatsPulse, {
            |out = 0, freq = 220, chaosAmount = 3.9, seed = 0.5,
            amp = 0.1, pan = 0, decay = 0.2|
            var chaos, carrier, envelope, signal;

            chaos = ChaosOsc.ar(chaosAmount, seed);
            carrier = SinOsc.ar(freq * (1.0 + (chaos * 0.012)));
            envelope = EnvGen.kr(
                Env.perc(0.005, decay, 1.0, -4.0),
                doneAction: 2
            );
            signal = (carrier * 0.72) + (chaos * 0.18);
            Out.ar(out, Pan2.ar(signal * amp * envelope, pan));
        });

        events = List.new;
        events.add([0.0, [\d_recv, droneDef.asBytes]]);
        events.add([0.0, [\d_recv, pulseDef.asBytes]]);
        events.add([
            0.01,
            [
                \s_new, \maxxedBeatsDrone, 1000, 0, 0,
                \freq, 55,
                \seed, seedValue,
                \amp, 0.12,
                \pan, 0.0,
                \gate, 1
            ]
        ]);

        stepCount.do { |step|
            var noteIndex, semitones, frequency, pulseSeed;
            var eventTime, velocity, pan, decay, chaosAmount;

            noteIndex = (step + rotation) % scale.size;
            semitones = scale.at(noteIndex);
            frequency = 110 * semitones.midiratio;
            pulseSeed = (((seedValue + (step * 0.173)) % 0.8) + 0.1)
                .clip(0.1, 0.9);
            eventTime = 0.05 + (step * stepDuration);
            velocity = if(step % 4 == 0, { 0.13 }, { 0.075 });
            pan = ((step % 5) - 2) * 0.25;
            decay = if(step % 4 == 0, { 0.34 }, { 0.2 });
            chaosAmount = if(step % 4 == 0, { 3.93 }, { 3.78 });

            events.add([
                eventTime,
                [
                    \s_new, \maxxedBeatsPulse, 2000 + step, 0, 0,
                    \freq, frequency,
                    \chaosAmount, chaosAmount,
                    \seed, pulseSeed,
                    \amp, velocity,
                    \pan, pan,
                    \decay, decay
                ]
            ]);
        };

        events.add([
            totalSeconds - 0.45,
            [\n_set, 1000, \gate, 0]
        ]);
        events.add([totalSeconds, [\c_set, 0, 0]]);

        ^Score(events.asArray);
    }
}
