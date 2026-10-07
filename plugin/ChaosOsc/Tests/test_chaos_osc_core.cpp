// Unit tests for the ChaosOsc DSP core (plugin/ChaosOsc/Source/ChaosOscCore.hpp).
//
// This core is plain C++ with no SuperCollider dependency, so it can be
// compiled and run without sclang/scsynth. It specifies the observable DSP
// contract that the SC plugin wrapper (SCUnit subclass) must preserve:
// bounded output, determinism for a fixed seed, finiteness under out-of-range
// parameters, escape from the map's degenerate fixed points, and the
// iteration-rate (`freq`) control: the default rate reproduces the original
// one-map-step-per-sample output bit-exactly, lower rates linearly
// interpolate between successive map states, and non-positive rates hold.
//
// Build/run: see plugin/ChaosOsc/Tests/run_tests.sh

#include "../Source/ChaosOscCore.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <limits>
#include <vector>

namespace {

int g_failures = 0;

constexpr double kSampleRate = 48000.0;
constexpr double kInfinity = std::numeric_limits<double>::infinity();
constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

// Reference model of the ChaosOsc DSP before the iteration-rate control was
// added (base commit fa6decd): exactly one logistic-map step per output
// sample. The default rate must reproduce it bit-exactly so existing
// compositions render unchanged.
class LegacyReference {
public:
    explicit LegacyReference(double seed) : state_(seed) {}

    double next(double chaosAmount) {
        const double r = chaososc::clampChaosAmount(chaosAmount);
        state_ = r * state_ * (1.0 - state_);
        return state_ * 2.0 - 1.0;
    }

    double state() const { return state_; }

private:
    double state_;
};

// A deterministic, per-sample-varying chaosAmount pattern that includes
// in-range values, out-of-range values, and NaN.
double variedChaosAmount(int index) {
    static const double amounts[] = {3.57, 3.7, 3.9, 3.999, 10.0, -5.0,
                                     3.82, kNaN, 3.95};
    return amounts[index % 9];
}

bool inAudioRange(double y) { return std::isfinite(y) && y >= -1.0 && y <= 1.0; }

void expect(bool condition, const char* description) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", description);
        ++g_failures;
    } else {
        std::printf("PASS: %s\n", description);
    }
}

void test_output_is_bounded_and_finite() {
    chaososc::ChaosOscCore core;
    core.reset(0.2);
    bool allBounded = true;
    bool allFinite = true;
    for (int i = 0; i < 100000; ++i) {
        const double y = core.next(3.9);
        if (y < -1.0 || y > 1.0) allBounded = false;
        if (!std::isfinite(y)) allFinite = false;
    }
    expect(allBounded, "output stays within [-1, 1] over 100000 samples");
    expect(allFinite, "output stays finite over 100000 samples");
}

void test_deterministic_for_fixed_seed_and_params() {
    chaososc::ChaosOscCore a;
    chaososc::ChaosOscCore b;
    a.reset(0.37);
    b.reset(0.37);

    std::vector<double> seqA;
    std::vector<double> seqB;
    for (int i = 0; i < 1000; ++i) {
        seqA.push_back(a.next(3.85));
        seqB.push_back(b.next(3.85));
    }
    expect(seqA == seqB,
           "same seed and chaosAmount produce an identical sample sequence");
}

void test_out_of_range_chaos_amount_is_clamped_and_stable() {
    chaososc::ChaosOscCore core;
    core.reset(0.5);
    bool allBounded = true;
    bool allFinite = true;
    for (int i = 0; i < 10000; ++i) {
        // 10.0 and -5.0 are far outside the documented chaotic range and must
        // be clamped internally rather than destabilizing the map.
        const double y = core.next(i % 2 == 0 ? 10.0 : -5.0);
        if (y < -1.0 || y > 1.0) allBounded = false;
        if (!std::isfinite(y)) allFinite = false;
    }
    expect(allBounded, "out-of-range chaosAmount is clamped to bounded output");
    expect(allFinite, "out-of-range chaosAmount keeps output finite");
}

void test_seed_edge_values_escape_fixed_points() {
    chaososc::ChaosOscCore core;
    core.reset(0.0);
    bool sawVariation = false;
    double first = core.next(3.9);
    for (int i = 0; i < 100; ++i) {
        const double y = core.next(3.9);
        if (std::fabs(y - first) > 1e-9) {
            sawVariation = true;
            break;
        }
    }
    expect(sawVariation,
           "seeding at the map's fixed point (0.0) still escapes into "
           "varying output instead of sticking");
}

void test_nan_chaos_amount_uses_minimum() {
    chaososc::ChaosOscCore nanControlCore;
    chaososc::ChaosOscCore minimumControlCore;
    nanControlCore.reset(0.37);
    minimumControlCore.reset(0.37);

    const double nanOutput =
        nanControlCore.next(std::numeric_limits<double>::quiet_NaN());
    const double minimumOutput =
        minimumControlCore.next(chaososc::kMinChaosAmount);
    expect(std::isfinite(nanOutput) && nanOutput == minimumOutput,
           "NaN chaosAmount falls back to the minimum and keeps output finite");
}

void test_nan_seed_uses_default_state() {
    chaososc::ChaosOscCore nanSeedCore;
    chaososc::ChaosOscCore defaultCore;
    nanSeedCore.reset(std::numeric_limits<double>::quiet_NaN());

    bool matchesDefaultSequence = true;
    for (int i = 0; i < 100; ++i) {
        if (nanSeedCore.next(3.9) != defaultCore.next(3.9)) {
            matchesDefaultSequence = false;
            break;
        }
    }
    expect(matchesDefaultSequence,
           "NaN seed falls back to the default midpoint state");
}

void test_block_processing_reads_audio_rate_control_per_sample() {
    const float controls[] = {3.57f, 3.9f, 3.999f, 3.6f};
    float blockOutput[4]{};

    chaososc::ChaosOscCore blockCore;
    blockCore.reset(0.37);
    chaososc::processBlock(blockCore, controls, blockOutput, 4);

    chaososc::ChaosOscCore sampleCore;
    sampleCore.reset(0.37);
    bool matchesPerSampleControls = true;
    for (int i = 0; i < 4; ++i) {
        const double expected = sampleCore.next(controls[i]);
        if (std::fabs(blockOutput[i] - expected) > 1e-6) {
            matchesPerSampleControls = false;
        }
    }
    expect(matchesPerSampleControls,
           "block processing applies chaosAmount independently per sample");
}

void test_iteration_increment_maps_freq_to_phase_step() {
    using chaososc::iterationIncrement;
    expect(iterationIncrement(kInfinity, kSampleRate) == 1.0 &&
               iterationIncrement(kSampleRate, kSampleRate) == 1.0 &&
               iterationIncrement(2.0 * kSampleRate, kSampleRate) == 1.0 &&
               iterationIncrement(1.0e30, kSampleRate) == 1.0,
           "freq >= sample rate (including inf) advances once per sample");
    expect(iterationIncrement(kNaN, kSampleRate) == 1.0,
           "NaN freq falls back to the default once-per-sample increment");
    expect(iterationIncrement(0.0, kSampleRate) == 0.0 &&
               iterationIncrement(-0.0, kSampleRate) == 0.0 &&
               iterationIncrement(-1.0, kSampleRate) == 0.0 &&
               iterationIncrement(-kInfinity, kSampleRate) == 0.0,
           "freq <= 0 (including -inf) maps to a hold (zero increment)");
    expect(iterationIncrement(100.0, kSampleRate) == 100.0 / kSampleRate &&
               iterationIncrement(12000.0, kSampleRate) == 0.25 &&
               iterationIncrement(10.0, 750.0) == 10.0 / 750.0,
           "0 < freq < sample rate maps to freq / sampleRate");
    expect(iterationIncrement(100.0, 0.0) == 1.0 &&
               iterationIncrement(100.0, kNaN) == 1.0 &&
               iterationIncrement(100.0, -kSampleRate) == 1.0 &&
               iterationIncrement(100.0, kInfinity) == 1.0,
           "an invalid sample rate falls back to the default increment");
    expect(chaososc::kDefaultIterationRate == kInfinity &&
               iterationIncrement(chaososc::kDefaultIterationRate, 750.0) ==
                   1.0,
           "the default iteration rate is +inf (once per sample at any rate)");
}

void test_default_rate_matches_legacy_output_bit_exactly() {
    struct RateCase {
        bool setRate;
        double freq;
        double sampleRate;
        const char* description;
    };
    const RateCase cases[] = {
        {false, 0.0, 0.0,
         "a core whose rate was never set matches the legacy output "
         "bit-exactly"},
        {true, chaososc::kDefaultIterationRate, kSampleRate,
         "the default freq (+inf) matches the legacy output bit-exactly"},
        {true, kSampleRate, kSampleRate,
         "freq == sample rate matches the legacy output bit-exactly"},
        {true, 4.0 * kSampleRate, kSampleRate,
         "freq above the sample rate matches the legacy output bit-exactly"},
        {true, 750.0, 750.0,
         "freq == control rate (.kr) matches the legacy output bit-exactly"},
        {true, kNaN, kSampleRate,
         "NaN freq matches the legacy output bit-exactly"},
    };
    for (const RateCase& rateCase : cases) {
        chaososc::ChaosOscCore core;
        core.reset(0.37);
        if (rateCase.setRate) {
            core.setIterationRate(rateCase.freq, rateCase.sampleRate);
        }
        LegacyReference legacy(0.37);
        bool identical = true;
        for (int i = 0; i < 20000; ++i) {
            const double amount = variedChaosAmount(i);
            if (core.next(amount) != legacy.next(amount) ||
                core.state() != legacy.state()) {
                identical = false;
                break;
            }
        }
        expect(identical, rateCase.description);
    }
}

void test_default_rate_block_processing_matches_legacy_bit_exactly() {
    constexpr int kBlock = 64;
    float controls[kBlock];
    for (int i = 0; i < kBlock; ++i) {
        controls[i] = static_cast<float>(3.57 + 0.4 * i / kBlock);
    }

    chaososc::ChaosOscCore audioRateCore;
    chaososc::ChaosOscCore scalarCore;
    audioRateCore.reset(0.61);
    scalarCore.reset(0.61);
    LegacyReference audioRateLegacy(static_cast<double>(0.61));
    LegacyReference scalarLegacy(static_cast<double>(0.61));

    bool audioRateIdentical = true;
    bool scalarIdentical = true;
    float audioRateOutput[kBlock];
    float scalarOutput[kBlock];
    for (int block = 0; block < 100; ++block) {
        audioRateCore.setIterationRate(chaososc::kDefaultIterationRate,
                                       kSampleRate);
        scalarCore.setIterationRate(chaososc::kDefaultIterationRate,
                                    kSampleRate);
        chaososc::processBlock(audioRateCore, controls, audioRateOutput,
                               kBlock);
        chaososc::processBlock(scalarCore, 3.9f, scalarOutput, kBlock);
        for (int i = 0; i < kBlock; ++i) {
            if (audioRateOutput[i] !=
                static_cast<float>(audioRateLegacy.next(controls[i]))) {
                audioRateIdentical = false;
            }
            if (scalarOutput[i] !=
                static_cast<float>(scalarLegacy.next(3.9f))) {
                scalarIdentical = false;
            }
        }
    }
    expect(audioRateIdentical,
           "default-rate per-sample block output matches the legacy float "
           "output bit-exactly");
    expect(scalarIdentical,
           "default-rate constant-amount block output matches the legacy "
           "float output bit-exactly");
}

void test_low_rate_interpolates_linearly_between_map_states() {
    // freq = sampleRate / 4 => the map advances every 4th output sample and
    // the output walks linearly from one map state to the next.
    chaososc::ChaosOscCore core;
    core.reset(0.37);
    core.setIterationRate(kSampleRate / 4.0, kSampleRate);
    LegacyReference legacy(0.37);

    bool reachesMapStates = true;
    bool interpolatesLinearly = true;
    bool advancesEveryFourth = true;
    double from = 0.37;
    for (int k = 0; k < 2000; ++k) {
        legacy.next(3.9);
        const double to = legacy.state();
        for (int j = 0; j < 4; ++j) {
            const double y = core.next(3.9);
            const double fraction = (j + 1) / 4.0;
            const double expected = (from + (to - from) * fraction) * 2.0 - 1.0;
            if (j == 3 && y != to * 2.0 - 1.0) reachesMapStates = false;
            if (std::fabs(y - expected) > 1e-12) interpolatesLinearly = false;
            if (core.state() != to) advancesEveryFourth = false;
        }
        from = to;
    }
    expect(reachesMapStates,
           "at freq < sample rate the output reaches each map state exactly");
    expect(interpolatesLinearly,
           "at freq < sample rate the output linearly interpolates between "
           "successive map states");
    expect(advancesEveryFourth,
           "freq = sampleRate / 4 advances the map once every 4 samples");
}

void test_low_rate_is_smooth_and_follows_the_full_rate_trajectory() {
    // 100 Hz at 48 kHz: one map step per 480 output samples.
    const double increment = 100.0 / kSampleRate;
    chaososc::ChaosOscCore core;
    core.reset(0.37);
    core.setIterationRate(100.0, kSampleRate);
    LegacyReference legacy(0.37);

    constexpr int kSamples = 48000;
    std::vector<double> output;
    output.reserve(kSamples);
    bool followsTrajectory = true;
    int advances = 0;
    double lastState = core.state();
    for (int i = 0; i < kSamples; ++i) {
        output.push_back(core.next(3.9));
        if (core.state() != lastState) {
            ++advances;
            legacy.next(3.9);
            if (core.state() != legacy.state()) followsTrajectory = false;
            lastState = core.state();
        }
    }

    double maxDelta = 0.0;
    int kinks = 0;
    bool bounded = true;
    for (int i = 0; i < kSamples; ++i) {
        if (!inAudioRange(output[i])) bounded = false;
        if (i > 0) {
            maxDelta = std::fmax(maxDelta, std::fabs(output[i] - output[i - 1]));
        }
        if (i > 1) {
            const double secondDifference =
                output[i] - 2.0 * output[i - 1] + output[i - 2];
            if (std::fabs(secondDifference) > 1e-9) ++kinks;
        }
    }
    expect(followsTrajectory,
           "a low iteration rate visits the same map states as the full rate");
    expect(std::abs(advances - 100) <= 1,
           "freq = 100 Hz advances the map ~100 times per 48000 samples");
    expect(maxDelta <= 2.0 * increment + 1e-12,
           "freq = 100 Hz keeps every per-sample step <= 2 * freq / sampleRate");
    // A map step falls between two output samples, so each step bends the
    // slope at (at most) the two samples around it.
    expect(kinks <= 2 * advances + 1,
           "freq = 100 Hz output is piecewise linear (slope changes only "
           "where the map advances)");
    expect(bounded, "low-rate output stays finite and within [-1, 1]");
}

void test_non_positive_rate_holds_the_current_value() {
    const double holdRates[] = {0.0, -1.0, -kInfinity};
    for (double holdRate : holdRates) {
        chaososc::ChaosOscCore core;
        core.reset(0.37);
        core.setIterationRate(100.0, kSampleRate);
        double last = 0.0;
        for (int i = 0; i < 1000; ++i) last = core.next(3.9);  // mid-segment
        const double heldState = core.state();

        core.setIterationRate(holdRate, kSampleRate);
        bool held = true;
        for (int i = 0; i < 5000; ++i) {
            if (core.next(3.9) != last || core.state() != heldState) {
                held = false;
            }
        }
        expect(held, "freq <= 0 holds the current interpolated output value");

        core.setIterationRate(100.0, kSampleRate);
        const double resumed = core.next(3.9);
        expect(std::fabs(resumed - last) <= 2.0 * 100.0 / kSampleRate &&
                   resumed != last,
               "resuming from a hold continues smoothly from the held value");
    }

    chaososc::ChaosOscCore fullRateCore;
    fullRateCore.reset(0.37);
    double lastFullRate = 0.0;
    for (int i = 0; i < 777; ++i) lastFullRate = fullRateCore.next(3.9);
    fullRateCore.setIterationRate(0.0, kSampleRate);
    bool heldFullRate = true;
    for (int i = 0; i < 1000; ++i) {
        if (fullRateCore.next(3.9) != lastFullRate) heldFullRate = false;
    }
    expect(heldFullRate,
           "freq <= 0 after full-rate output holds the last sample exactly");

    chaososc::ChaosOscCore freshCore;
    freshCore.reset(0.37);
    freshCore.setIterationRate(0.0, kSampleRate);
    bool heldSeed = true;
    for (int i = 0; i < 100; ++i) {
        if (freshCore.next(3.9) != 0.37 * 2.0 - 1.0) heldSeed = false;
    }
    expect(heldSeed, "freq <= 0 from the start holds the seed value");
}

void test_nan_rate_uses_default_behaviour_after_a_low_rate() {
    chaososc::ChaosOscCore core;
    core.reset(0.37);
    core.setIterationRate(100.0, kSampleRate);
    for (int i = 0; i < 1000; ++i) core.next(3.9);

    core.setIterationRate(kNaN, kSampleRate);
    LegacyReference legacy(core.state());
    bool matchesDefault = true;
    for (int i = 0; i < 1000; ++i) {
        if (core.next(3.9) != legacy.next(3.9)) matchesDefault = false;
    }
    expect(matchesDefault,
           "switching freq to NaN resumes one map step per output sample");
}

void test_chaos_amount_applies_only_when_the_map_advances() {
    // At freq = sampleRate / 4 the map advances on samples 0, 4, 8, ...
    chaososc::ChaosOscCore constantAmount;
    chaososc::ChaosOscCore ignoredBetweenSteps;
    chaososc::ChaosOscCore changedOnSteps;
    for (chaososc::ChaosOscCore* core :
         {&constantAmount, &ignoredBetweenSteps, &changedOnSteps}) {
        core->reset(0.37);
        core->setIterationRate(kSampleRate / 4.0, kSampleRate);
    }
    bool ignoredBetween = true;
    bool appliedOnSteps = false;
    for (int i = 0; i < 4000; ++i) {
        const bool advancing = i % 4 == 0;
        const double reference = constantAmount.next(3.9);
        if (ignoredBetweenSteps.next(advancing ? 3.9 : 3.6) != reference) {
            ignoredBetween = false;
        }
        if (changedOnSteps.next(advancing ? 3.6 : 3.9) != reference) {
            appliedOnSteps = true;
        }
    }
    expect(ignoredBetween,
           "chaosAmount between map steps does not affect interpolated output");
    expect(appliedOnSteps,
           "chaosAmount at map steps changes the interpolated trajectory");
}

void test_switching_to_a_low_rate_is_continuous() {
    chaososc::ChaosOscCore core;
    core.reset(0.37);
    double last = 0.0;
    for (int i = 0; i < 100; ++i) last = core.next(3.9);
    core.setIterationRate(0.01 * kSampleRate, kSampleRate);
    const double first = core.next(3.9);
    expect(std::fabs(first - last) <= 2.0 * 0.01 + 1e-12,
           "switching from full rate to a low rate starts from the last output");

    chaososc::ChaosOscCore seeded;
    seeded.reset(0.37);
    seeded.setIterationRate(100.0, kSampleRate);
    const double firstSeeded = seeded.next(3.9);
    expect(std::fabs(firstSeeded - (0.37 * 2.0 - 1.0)) <=
               2.0 * 100.0 / kSampleRate,
           "a low rate starts interpolating from the seed after reset");
}

void test_rate_schedule_is_deterministic_and_bounded() {
    const double schedule[] = {kInfinity, 100.0,    0.0,     3000.0,
                               kNaN,      -1.0,     47999.0, 48000.0,
                               1.0e-3,    24000.0,  1.0,     96000.0};
    static constexpr int kBlock = 64;
    auto render = [&](double seed) {
        chaososc::ChaosOscCore core;
        core.reset(seed);
        std::vector<float> rendered;
        float block[kBlock];
        float controls[kBlock];
        int sample = 0;
        for (int repeat = 0; repeat < 20; ++repeat) {
            for (double freq : schedule) {
                core.setIterationRate(freq, kSampleRate);
                for (int i = 0; i < kBlock; ++i) {
                    controls[i] =
                        static_cast<float>(variedChaosAmount(sample++));
                }
                chaososc::processBlock(core, controls, block, kBlock);
                rendered.insert(rendered.end(), block, block + kBlock);
            }
        }
        return rendered;
    };

    const std::vector<float> first = render(0.37);
    const std::vector<float> second = render(0.37);
    const std::vector<float> otherSeed = render(0.73);
    bool bounded = true;
    for (float y : first) {
        if (!inAudioRange(y)) bounded = false;
    }
    expect(first == second,
           "an identical seed and rate schedule reproduce identical output");
    expect(first != otherSeed,
           "a different seed changes the output under a rate schedule");
    expect(bounded,
           "output stays finite and within [-1, 1] across rate changes and "
           "out-of-range controls");
}

}  // namespace

int main() {
    test_output_is_bounded_and_finite();
    test_deterministic_for_fixed_seed_and_params();
    test_out_of_range_chaos_amount_is_clamped_and_stable();
    test_seed_edge_values_escape_fixed_points();
    test_nan_chaos_amount_uses_minimum();
    test_nan_seed_uses_default_state();
    test_block_processing_reads_audio_rate_control_per_sample();
    test_iteration_increment_maps_freq_to_phase_step();
    test_default_rate_matches_legacy_output_bit_exactly();
    test_default_rate_block_processing_matches_legacy_bit_exactly();
    test_low_rate_interpolates_linearly_between_map_states();
    test_low_rate_is_smooth_and_follows_the_full_rate_trajectory();
    test_non_positive_rate_holds_the_current_value();
    test_nan_rate_uses_default_behaviour_after_a_low_rate();
    test_chaos_amount_applies_only_when_the_map_advances();
    test_switching_to_a_low_rate_is_continuous();
    test_rate_schedule_is_deterministic_and_bounded();

    if (g_failures > 0) {
        std::fprintf(stderr, "\n%d test(s) failed\n", g_failures);
        return 1;
    }
    std::printf("\nAll tests passed\n");
    return 0;
}
