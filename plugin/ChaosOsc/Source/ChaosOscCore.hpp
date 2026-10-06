// ChaosOsc DSP core: a logistic-map chaotic oscillator.
//
// This is the initial entry in the product's distinctive sound-design
// palette (see docs/decision_log.md for the selection rationale). The core is
// plain, dependency-free C++ so it can be unit tested without a
// SuperCollider build environment. The SC plugin wrapper (an SCUnit subclass
// built against SC_PlugIn.hpp) sets the iteration rate once per block and
// then calls `next()`/`processBlock()` once per output sample. Nothing here
// allocates, performs I/O, locks, or blocks, so it is real-time safe by
// construction.
//
// DSP behavior: the logistic map x[n+1] = r * x[n] * (1 - x[n]) is chaotic
// for r roughly in [3.57, 4.0]. Its trajectory is bounded to [0, 1] for any
// seed also in [0, 1] (excluding the unstable fixed points), so scaling it to
// [-1, 1] gives a deterministic, seed-controlled, broadband, non-periodic
// signal distinct from standard oscillator/noise UGens. The scaled output is
// not zero-mean (for example about +0.19 at r = 3.9); see the help file for
// the recommended LeakDC idiom.
//
// Iteration rate ("freq"): by default the map advances once per output
// sample. A finite rate below the unit's sample rate advances the map at
// that rate (a double-precision phase accumulator) and linearly interpolates
// between successive map states, turning the same trajectory into a smooth
// modulation source. A rate <= 0 holds the current output value.
#pragma once

#include <cmath>
#include <limits>

namespace chaososc {

// Bounds for the logistic-map growth-rate ("chaosAmount") control. Values
// below kMinChaosAmount settle into a fixed point or low-period cycle
// (not chaotic); values above kMaxChaosAmount approach the map's domain
// boundary where floating-point rounding can push the state out of [0, 1].
constexpr double kMinChaosAmount = 3.57;
constexpr double kMaxChaosAmount = 3.999;

// Default map-iteration rate in Hz. Any rate at or above the unit's sample
// rate advances the map once per output sample, which reproduces the
// original (pre-rate-control) output bit-exactly; +inf does so at every
// server sample rate and calculation rate.
constexpr double kDefaultIterationRate = std::numeric_limits<double>::infinity();

// Clamps a requested chaosAmount into the documented chaotic range. Kept
// free of any external dependency so the core stays trivially unit
// testable and safe to call from the audio thread.
inline double clampChaosAmount(double amount) {
    if (std::isnan(amount)) return kMinChaosAmount;
    if (amount < kMinChaosAmount) return kMinChaosAmount;
    if (amount > kMaxChaosAmount) return kMaxChaosAmount;
    return amount;
}

// Converts a requested iteration rate (map steps per second) into the phase
// increment per output sample at the given sample rate:
//   1.0              -> advance once per output sample (freq >= sampleRate,
//                       NaN freq, or an unusable sample rate);
//   0.0              -> hold the current value (freq <= 0, including -inf);
//   freq/sampleRate  -> interpolate between map steps (0 < freq < sampleRate).
inline double iterationIncrement(double freq, double sampleRate) {
    if (std::isnan(freq)) return 1.0;
    if (freq <= 0.0) return 0.0;
    if (!(sampleRate > 0.0) || !std::isfinite(sampleRate)) return 1.0;
    if (freq >= sampleRate) return 1.0;
    const double increment = freq / sampleRate;
    return increment < 1.0 ? increment : 1.0;
}

// Header-only core of the ChaosOsc UGen. Holds the map's scalar state plus
// the interpolation segment it is currently traversing: the output walks
// from `previous_` (map step k) to `state_` (map step k + 1) as `phase_`
// goes from 0 to 1. `reset` seeds it, `setIterationRate` selects the rate,
// and `next` produces one output sample.
class ChaosOscCore {
public:
    // Seeds the internal state for the next call to `next()`. The logistic
    // map has fixed points at exactly 0.0 and 1.0 (and passes through 0.5
    // deterministically at r == 4.0 only after many iterations); seeding
    // audio-thread-called `next()` at exactly 0.0 or 1.0 would produce
    // silence forever, so those exact edges are nudged into the open
    // interval. The output restarts exactly at the seed (phase 1 of an
    // empty segment); the iteration rate is left unchanged.
    void reset(double seed) {
        if (std::isnan(seed)) seed = 0.5;
        if (seed <= 0.0) seed = 1e-6;
        if (seed >= 1.0) seed = 1.0 - 1e-6;
        previous_ = seed;
        state_ = seed;
        phase_ = 1.0;
    }

    // Selects the map-iteration rate (Hz) relative to the unit's sample rate
    // (see `iterationIncrement`). Cheap enough to call once per block.
    void setIterationRate(double freq, double sampleRate) {
        increment_ = iterationIncrement(freq, sampleRate);
    }

    // Produces the next output sample in [-1, 1]. `chaosAmount` (clamped
    // internally) is only used when the map advances on this sample.
    double next(double chaosAmount) {
        if (increment_ >= 1.0) {
            advance(chaosAmount);
            phase_ = 1.0;
        } else if (increment_ > 0.0) {
            phase_ += increment_;
            if (phase_ > 1.0) {
                phase_ -= 1.0;
                advance(chaosAmount);
            }
        }
        return value() * 2.0 - 1.0;
    }

    // Exposes the most recent raw [0, 1] map state, mainly for
    // tests/introspection.
    double state() const { return state_; }

private:
    void advance(double chaosAmount) {
        const double r = clampChaosAmount(chaosAmount);
        previous_ = state_;
        state_ = r * state_ * (1.0 - state_);
    }

    // The current [0, 1] output position. At the end of a segment this is
    // exactly the latest map state, so once-per-sample output is unchanged
    // by the interpolation arithmetic.
    double value() const {
        if (phase_ >= 1.0) return state_;
        return previous_ + (state_ - previous_) * phase_;
    }

    double previous_ = 0.5;
    double state_ = 0.5;
    double phase_ = 1.0;
    double increment_ = 1.0;
};

// Renders one block with a per-sample (audio-rate) chaosAmount.
inline void processBlock(ChaosOscCore& core,
                         const float* chaosAmounts,
                         float* output,
                         int nSamples) {
    for (int i = 0; i < nSamples; ++i) {
        output[i] = static_cast<float>(core.next(chaosAmounts[i]));
    }
}

// Renders one block with a chaosAmount that is constant for the block
// (scalar or control-rate input).
inline void processBlock(ChaosOscCore& core,
                         float chaosAmount,
                         float* output,
                         int nSamples) {
    for (int i = 0; i < nSamples; ++i) {
        output[i] = static_cast<float>(core.next(chaosAmount));
    }
}

}  // namespace chaososc
