// Logistic-map chaotic oscillator (server plugin: plugin/ChaosOsc/Source).
// freq is the map-iteration rate in Hz. The default, inf, advances the map
// once per output sample, which keeps two-argument calls bit-identical to the
// original ChaosOsc.ar(chaosAmount, seed). See ChaosOsc.schelp.
ChaosOsc : UGen {
    *ar { |chaosAmount = 3.9, seed = 0.5, freq = inf, mul = 1.0, add = 0.0|
        ^this.multiNew('audio', chaosAmount, seed, freq).madd(mul, add)
    }

    *kr { |chaosAmount = 3.9, seed = 0.5, freq = inf, mul = 1.0, add = 0.0|
        ^this.multiNew('control', chaosAmount, seed, freq).madd(mul, add)
    }
}
