// ChaosOsc SuperCollider server plugin: the UGen wrapper around the
// dependency-free, unit-tested `chaososc::ChaosOscCore` (see
// ChaosOscCore.hpp and docs/plugin/SOUND_DESIGN.md for the DSP rationale).
//
// This file is intentionally thin: all chaotic-map math lives in
// ChaosOscCore.hpp so it stays testable without the SuperCollider
// toolchain. This wrapper only does per-sample plumbing (reading unit
// inputs/outputs and driving the core once per sample), which is what
// SC_PlugIn.hpp's SCUnit base class expects of a UGen's calc function. It
// performs no I/O, allocation, locking, or blocking calls in `next()`, so
// it is safe to run on the real-time audio thread.
//
// sclang-facing controls (see ChaosOsc.sc / ChaosOsc.schelp):
//   ChaosOsc.ar(chaosAmount, seed)
//     chaosAmount: logistic-map growth rate, clamped internally to
//                  [3.57, 3.999] (see ChaosOscCore::clampChaosAmount).
//                  Audio-rate inputs are read per sample; scalar and control-
//                  rate inputs are broadcast across the current audio block.
//     seed:        initial map state in (0, 1), read once at Ctor time.
//                  Not re-read per sample; changing the seed input after
//                  the synth has started has no effect (this is
//                  intentional -- see docs/plugin/SOUND_DESIGN.md).

#include "SC_PlugIn.hpp"

#include "ChaosOscCore.hpp"

static InterfaceTable* ft;

class ChaosOsc : public SCUnit {
public:
    ChaosOsc();

private:
    void next(int nSamples);

    chaososc::ChaosOscCore mCore;
};

ChaosOsc::ChaosOsc() {
    const float seed = in0(1);
    mCore.reset(seed);

    set_calc_function<ChaosOsc, &ChaosOsc::next>();
}

void ChaosOsc::next(int nSamples) {
    float* outBuf = out(0);
    if (isAudioRateIn(0)) {
        chaososc::processBlock(mCore, in(0), outBuf, nSamples);
        return;
    }

    const float chaosAmount = in0(0);
    for (int i = 0; i < nSamples; ++i) {
        outBuf[i] = static_cast<float>(mCore.next(chaosAmount));
    }
}

PluginLoad(ChaosOscUGens) {
    ft = inTable;
    registerUnit<ChaosOsc>(ft, "ChaosOsc", false);
}
