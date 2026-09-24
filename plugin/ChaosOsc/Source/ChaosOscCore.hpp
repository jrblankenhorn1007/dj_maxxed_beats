// ChaosOsc DSP core: a logistic-map chaotic oscillator.
//
// This is the initial entry in the product's distinctive sound-design
// palette (see docs/decision_log.md for the selection rationale). The core is
// plain, dependency-free C++ so it can be unit tested without a
// SuperCollider build environment. The SC plugin wrapper (a UGen subclass
// built against SC_PlugIn.hpp) calls `processBlock()` with audio-rate control
// and output buffers. It does no I/O, allocation, or blocking calls, so it
// is real-time safe by construction.
//
// DSP behavior: the logistic map x[n+1] = r * x[n] * (1 - x[n]) is chaotic
// for r roughly in [3.57, 4.0]. Its trajectory is bounded to [0, 1] for any
// seed also in [0, 1] (excluding the unstable fixed points), so scaling it to
// [-1, 1] gives a deterministic, seed-controlled, broadband, non-periodic
// audio signal distinct from standard oscillator/noise UGens.
#pragma once

namespace chaososc {

// Bounds for the logistic-map growth-rate ("chaosAmount") control. Values
// below kMinChaosAmount settle into a fixed point or low-period cycle
// (not chaotic); values above kMaxChaosAmount approach the map's domain
// boundary where floating-point rounding can push the state out of [0, 1].
constexpr double kMinChaosAmount = 3.57;
constexpr double kMaxChaosAmount = 3.999;

// Clamps a requested chaosAmount into the documented chaotic range. Kept
// free of any external dependency so the core stays trivially unit
// testable and safe to call from the audio thread.
inline double clampChaosAmount(double amount) {
    if (amount < kMinChaosAmount) return kMinChaosAmount;
    if (amount > kMaxChaosAmount) return kMaxChaosAmount;
    return amount;
}

// Header-only core of the ChaosOsc UGen. Holds only the map's scalar state;
// `reset` seeds it and `next` advances one sample.
class ChaosOscCore {
public:
    // Seeds the internal state for the next call to `next()`. The logistic
    // map has fixed points at exactly 0.0 and 1.0 (and passes through 0.5
    // deterministically at r == 4.0 only after many iterations); seeding
    // audio-thread-called `next()` at exactly 0.0 or 1.0 would produce
    // silence forever, so those exact edges are nudged into the open
    // interval.
    void reset(double seed) {
        if (seed <= 0.0) seed = 1e-6;
        if (seed >= 1.0) seed = 1.0 - 1e-6;
        state_ = seed;
    }

    // Advances the logistic map by one step using the given chaosAmount
    // (clamped internally) and returns the next sample scaled from the
    // map's [0, 1] range to audio-rate [-1, 1].
    double next(double chaosAmount) {
        const double r = clampChaosAmount(chaosAmount);
        state_ = r * state_ * (1.0 - state_);
        return state_ * 2.0 - 1.0;
    }

    // Exposes the raw [0, 1] map state, mainly for tests/introspection.
    double state() const { return state_; }

private:
    double state_ = 0.5;
};

inline void processBlock(ChaosOscCore& core,
                         const float* chaosAmounts,
                         float* output,
                         int nSamples) {
    for (int i = 0; i < nSamples; ++i) {
        output[i] = static_cast<float>(core.next(chaosAmounts[i]));
    }
}

}  // namespace chaososc
