# SuperCollider guidance

## Verified project target

Use the project's documented initial runtime/API target, SuperCollider
3.14.1, unless the selected installation and its documentation establish a
different supported version. Do not imply that this version has been verified
on every target device: current plugin/NRT evidence is macOS arm64 only;
Windows 10 x64, an actual MacBook Neo, real-time audition, and other releases
remain unverified.

Prefer file-based `.scd` compositions and offline NRT rendering for the MVP.
Use ordinary SuperCollider language constructs and confirm unfamiliar
classes, methods, argument names, and plugin requirements in documentation for
the actual installed version. Do not invent or assume APIs from memory. Label
untested code and compatibility as unverified rather than presenting them as
working.

## ChaosOsc

The project's verified custom-UGen constructor is
`ChaosOsc.ar(chaosAmount, seed)`; its defaults are `3.9` and `0.5`. It returns
an audio-rate signal in `[-1, 1]`, so scale it appropriately when composing
with other signals. The plugin clamps `chaosAmount` to `[3.57, 3.999]`.
Audio-rate `chaosAmount` is read per sample; scalar and control-rate values
are broadcast per audio block, and control-rate changes take effect on the
next block. The seed is captured when the Synth is created; changing it later
does not reseed that Synth. Use the UGen only when the matching plugin and
language class are available. Do not describe the planned update-rate control
as implemented.

Keep provider calls, file access, project editing, and other blocking work out
of UGen/audio callbacks. Treat composition code as executable code, not as
data that is automatically safe to evaluate.
