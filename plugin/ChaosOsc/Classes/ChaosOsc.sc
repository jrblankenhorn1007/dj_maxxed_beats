ChaosOsc : UGen {
    *ar { |chaosAmount = 3.9, seed = 0.5|
        ^this.multiNew('audio', chaosAmount, seed)
    }
}
