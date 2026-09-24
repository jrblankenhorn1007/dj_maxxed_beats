// Unit tests for the ChaosOsc DSP core (plugin/ChaosOsc/Source/ChaosOscCore.hpp).
//
// This core is plain C++ with no SuperCollider dependency, so it can be
// compiled and run directly in this environment even though sclang/scsynth
// are not installed here. It specifies the observable DSP contract that the
// eventual SC plugin wrapper (UGen subclass) must preserve: bounded output,
// determinism for a fixed seed, finiteness under out-of-range parameters, and
// escape from the map's degenerate fixed points.
//
// Build/run: see plugin/ChaosOsc/Tests/run_tests.sh

#include "../Source/ChaosOscCore.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace {

int g_failures = 0;

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

}  // namespace

int main() {
    test_output_is_bounded_and_finite();
    test_deterministic_for_fixed_seed_and_params();
    test_out_of_range_chaos_amount_is_clamped_and_stable();
    test_seed_edge_values_escape_fixed_points();

    if (g_failures > 0) {
        std::fprintf(stderr, "\n%d test(s) failed\n", g_failures);
        return 1;
    }
    std::printf("\nAll tests passed\n");
    return 0;
}
