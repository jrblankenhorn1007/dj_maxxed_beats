"""Fast, toolchain-free unit tests for the ChaosOsc installer and CI helpers.

These cover the pure logic of scripts/install_chaososc.py (per-platform
default Extensions directory matching SuperCollider 3.14.1's
Platform.userExtensionDir, plugin binary naming, install marker detection),
scripts/ci_verify_plugin.py (PE export-table and dumpbin parsing used to
verify the Windows `load` export), and scripts/ci_nrt_smoke.py (sclang score
generation and float-WAV render validation). The real cmake/sclang/scsynth
flows are exercised by tests/test_chaososc_cmake_install.py.
"""

import importlib.util
import math
from pathlib import Path
import shutil
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRATCH_DIR = ROOT / "tests" / ".build" / "chaososc-install-scripts"


def load_script(name):
    path = ROOT / "scripts" / "{}.py".format(name)
    if not path.is_file():
        raise AssertionError("missing required script: {}".format(path))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fresh_scratch_dir(name):
    path = SCRATCH_DIR / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def build_pe_dll(export_names, machine=0x8664):
    """Builds a minimal, structurally valid PE32+ DLL image whose export
    directory lists `export_names` (no code; only headers and .edata)."""
    file_alignment = 0x200
    section_rva = 0x1000
    names = sorted(export_names)
    count = len(names)

    directory_size = 40
    functions_rva = section_rva + directory_size
    names_rva = functions_rva + 4 * count
    ordinals_rva = names_rva + 4 * count
    dll_name_rva = ordinals_rva + 2 * count
    dll_name = b"ChaosOsc.scx\0"
    strings_rva = dll_name_rva + len(dll_name)

    string_blob = b""
    name_rvas = []
    for name in names:
        name_rvas.append(strings_rva + len(string_blob))
        string_blob += name.encode("ascii") + b"\0"

    section = struct.pack(
        "<IIHHIIIIIII",
        0,
        0,
        0,
        0,
        dll_name_rva,
        1,
        count,
        count,
        functions_rva,
        names_rva,
        ordinals_rva,
    )
    section += b"".join(struct.pack("<I", 0x2000 + 16 * i) for i in range(count))
    section += b"".join(struct.pack("<I", rva) for rva in name_rvas)
    section += b"".join(struct.pack("<H", i) for i in range(count))
    section += dll_name + string_blob
    virtual_size = len(section)
    raw_size = (virtual_size + file_alignment - 1) // file_alignment * file_alignment
    section = section.ljust(raw_size, b"\0")

    dos_header = bytearray(64)
    dos_header[0:2] = b"MZ"
    struct.pack_into("<I", dos_header, 0x3C, 64)

    optional_header = bytearray(240)
    struct.pack_into("<H", optional_header, 0, 0x20B)
    struct.pack_into("<I", optional_header, 108, 16)
    struct.pack_into("<II", optional_header, 112, section_rva, virtual_size)

    coff_header = struct.pack(
        "<HHIIIHH", machine, 1, 0, 0, 0, len(optional_header), 0x2022
    )
    section_header = struct.pack(
        "<8sIIIIIIHHI",
        b".edata",
        virtual_size,
        section_rva,
        raw_size,
        file_alignment,
        0,
        0,
        0,
        0,
        0x40000040,
    )
    headers = bytes(dos_header) + b"PE\0\0" + coff_header
    headers += bytes(optional_header) + section_header
    return headers.ljust(file_alignment, b"\0") + section


def write_float_wav(path, channels, sample_rate, frames):
    samples = [sample for frame in frames for sample in frame]
    data = struct.pack("<{}f".format(len(samples)), *samples)
    fmt = struct.pack(
        "<HHIIHH",
        3,
        channels,
        sample_rate,
        sample_rate * channels * 4,
        channels * 4,
        32,
    )
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(data)) + data
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


class InstallerPlatformDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = load_script("install_chaososc")

    def test_macos_default_matches_sc_user_extension_dir(self):
        self.assertEqual(
            self.installer.default_extensions_dir(
                "darwin", {"HOME": "/Users/alice"}
            ),
            "/Users/alice/Library/Application Support/SuperCollider/Extensions",
        )

    def test_macos_honors_xdg_data_home_like_sclang(self):
        # SC 3.14.1's SC_Filesystem_macos.cpp prefers XDG_DATA_HOME.
        self.assertEqual(
            self.installer.default_extensions_dir(
                "darwin", {"HOME": "/Users/alice", "XDG_DATA_HOME": "/data"}
            ),
            "/data/SuperCollider/Extensions",
        )

    def test_linux_default_uses_xdg_data_home_or_local_share(self):
        self.assertEqual(
            self.installer.default_extensions_dir("linux", {"HOME": "/home/bob"}),
            "/home/bob/.local/share/SuperCollider/Extensions",
        )
        self.assertEqual(
            self.installer.default_extensions_dir(
                "linux", {"HOME": "/home/bob", "XDG_DATA_HOME": "/xdg"}
            ),
            "/xdg/SuperCollider/Extensions",
        )
        self.assertEqual(
            self.installer.default_extensions_dir(
                "linux", {"HOME": "/home/bob", "XDG_DATA_HOME": ""}
            ),
            "/home/bob/.local/share/SuperCollider/Extensions",
        )

    def test_windows_default_uses_local_app_data(self):
        self.assertEqual(
            self.installer.default_extensions_dir(
                "win32",
                {
                    "LOCALAPPDATA": "C:\\Users\\carol\\AppData\\Local",
                    "USERPROFILE": "C:\\Users\\carol",
                },
            ),
            "C:\\Users\\carol\\AppData\\Local\\SuperCollider\\Extensions",
        )
        self.assertEqual(
            self.installer.default_extensions_dir(
                "win32", {"USERPROFILE": "C:\\Users\\carol"}
            ),
            "C:\\Users\\carol\\AppData\\Local\\SuperCollider\\Extensions",
        )

    def test_missing_home_is_an_actionable_error(self):
        with self.assertRaises(self.installer.InstallerError) as raised:
            self.installer.default_extensions_dir("linux", {})
        self.assertIn("--extensions-dir", str(raised.exception))

    def test_plugin_binary_name_follows_sc_conventions(self):
        self.assertEqual(self.installer.plugin_binary_name("darwin"), "ChaosOsc.scx")
        self.assertEqual(self.installer.plugin_binary_name("win32"), "ChaosOsc.scx")
        self.assertEqual(self.installer.plugin_binary_name("linux"), "ChaosOsc.so")

    def test_marker_is_a_hidden_file_and_detects_only_marked_installs(self):
        marker = self.installer.MARKER_NAME
        self.assertTrue(marker.startswith("."), marker)
        self.assertFalse(marker.endswith((".sc", ".scx", ".so", ".schelp")))

        scratch = fresh_scratch_dir("marker")
        unmarked = scratch / "unmarked"
        unmarked.mkdir()
        marked = scratch / "marked"
        marked.mkdir()
        (marked / marker).write_text("x\n", encoding="utf-8")
        marker_dir = scratch / "marker-is-a-directory"
        (marker_dir / marker).mkdir(parents=True)

        self.assertTrue(self.installer.is_marked_install(marked))
        self.assertFalse(self.installer.is_marked_install(unmarked))
        self.assertFalse(self.installer.is_marked_install(marker_dir))
        self.assertFalse(self.installer.is_marked_install(scratch / "missing"))


class PluginVerifierParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_script("ci_verify_plugin")

    def test_reads_pe32_plus_export_names_and_machine(self):
        scratch = fresh_scratch_dir("pe")
        dll = scratch / "ChaosOsc.scx"
        dll.write_bytes(build_pe_dll(["load", "api_version", "server_type"]))

        machine, names = self.verifier.read_pe_exports(dll)

        self.assertEqual(machine, 0x8664)
        self.assertEqual(sorted(names), ["api_version", "load", "server_type"])

    def test_pe_without_load_export_is_rejected(self):
        scratch = fresh_scratch_dir("pe-no-load")
        dll = scratch / "ChaosOsc.scx"
        dll.write_bytes(build_pe_dll(["api_version", "server_type"]))

        with self.assertRaises(self.verifier.VerificationError) as raised:
            self.verifier.verify_windows_exports(dll)
        self.assertIn("load", str(raised.exception))

    def test_non_x64_pe_is_rejected(self):
        scratch = fresh_scratch_dir("pe-x86")
        dll = scratch / "ChaosOsc.scx"
        dll.write_bytes(build_pe_dll(["load"], machine=0x014C))

        with self.assertRaises(self.verifier.VerificationError) as raised:
            self.verifier.verify_windows_exports(dll)
        self.assertIn("x64", str(raised.exception))

    def test_non_pe_file_is_rejected(self):
        scratch = fresh_scratch_dir("not-pe")
        bogus = scratch / "ChaosOsc.scx"
        bogus.write_bytes(b"\x7fELF" + b"\0" * 60)

        with self.assertRaises(self.verifier.VerificationError):
            self.verifier.read_pe_exports(bogus)

    def test_macos_export_check_inspects_every_architecture_slice(self):
        commands = []
        listing = (
            "\nChaosOsc.scx (for architecture x86_64):\n"
            "0000000000001200 T _api_version\n"
            "\nChaosOsc.scx (for architecture arm64):\n"
            "0000000000001000 T _api_version\n"
            "0000000000001010 T _load\n"
        )

        def fake_run_tool(command):
            commands.append(command)
            return listing

        original = self.verifier.run_tool
        self.verifier.run_tool = fake_run_tool
        try:
            with self.assertRaises(self.verifier.VerificationError) as raised:
                self.verifier.verify_unix_exports("ChaosOsc.scx", "darwin")
        finally:
            self.verifier.run_tool = original

        self.assertEqual(commands, [["nm", "-gU", "-arch", "all", "ChaosOsc.scx"]])
        self.assertIn("x86_64", str(raised.exception))
        self.assertIn("_load", str(raised.exception))

    def test_parses_dumpbin_exports_listing(self):
        listing = (
            "Dump of file ChaosOsc.scx\n\n"
            "File Type: DLL\n\n"
            "  Section contains the following exports for ChaosOsc.scx\n\n"
            "    00000000 characteristics\n"
            "    FFFFFFFF time date stamp\n"
            "        0.00 version\n"
            "           1 ordinal base\n"
            "           3 number of functions\n"
            "           3 number of names\n\n"
            "    ordinal hint RVA      name\n\n"
            "          1    0 00001020 api_version\n"
            "          2    1 00001040 load\n"
            "          3    2 00001030 server_type\n\n"
            "  Summary\n\n"
            "        1000 .data\n"
        )
        self.assertEqual(
            self.verifier.parse_dumpbin_exports(listing),
            ["api_version", "load", "server_type"],
        )

    def test_nm_listing_parser_finds_global_text_symbols(self):
        listing = (
            "\nChaosOsc.scx (for architecture x86_64):\n"
            "0000000000003f30 T _api_version\n"
            "0000000000003f40 T _load\n"
            "\nChaosOsc.scx (for architecture arm64):\n"
            "0000000000003e30 T _api_version\n"
            "0000000000003e40 T _load\n"
            "0000000000008000 D _someData\n"
        )
        self.assertEqual(
            self.verifier.global_text_symbols(listing),
            {"_api_version", "_load"},
        )


class NrtSmokeHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = load_script("ci_nrt_smoke")

    def test_sc_path_literals_are_portable_and_escaped(self):
        self.assertEqual(
            self.smoke.sc_path_literal(
                "C:\\Users\\runner\\work\\score.osc", windows=True
            ),
            '"C:/Users/runner/work/score.osc"',
        )
        self.assertEqual(
            self.smoke.sc_path_literal('/work/odd "name"/x', windows=False),
            '"/work/odd \\"name\\"/x"',
        )
        self.assertEqual(
            self.smoke.sc_path_literal("/work/back\\slash", windows=False),
            '"/work/back\\\\slash"',
        )

    def test_score_source_uses_installed_class_and_reports_its_origin(self):
        source = self.smoke.build_score_source(
            "/work/score.osc", "/work/sclang-report.txt", windows=False
        )

        self.assertIn("ChaosOsc.ar(3.9, 0.37)", source)
        self.assertIn("Platform.userExtensionDir", source)
        self.assertIn("ChaosOsc.filenameSymbol", source)
        self.assertIn('"/work/score.osc"', source)
        self.assertIn('File.use("/work/sclang-report.txt"', source)
        self.assertIn(self.smoke.SCORE_WRITTEN, source)
        self.assertIn("writeOSCFile", source)
        self.assertIn("0.exit", source)
        self.assertNotIn("\\", source)

    def test_bootstrap_fails_fast_when_the_class_is_missing(self):
        source = self.smoke.build_bootstrap_source(
            "/work/score.scd", "/work/sclang-report.txt", windows=False
        )

        self.assertIn("'ChaosOsc'.asClass.isNil", source)
        self.assertIn(self.smoke.CLASS_MISSING, source)
        self.assertIn('File.use("/work/sclang-report.txt"', source)
        self.assertIn("1.exit", source)
        self.assertIn('executeFile("/work/score.scd")', source)
        self.assertNotIn("ChaosOsc.ar", source)
        self.assertNotIn("\\", source)

    def test_sclang_report_values_are_parsed_by_tag(self):
        report = "\n".join(
            [
                self.smoke.EXTENSION_DIR_PREFIX + "/home/x/Extensions",
                self.smoke.CLASS_FILE_PREFIX + "/home/x/Extensions/ChaosOsc/Classes/ChaosOsc.sc",
                self.smoke.SCORE_WRITTEN,
                "",
            ]
        )
        self.assertEqual(
            self.smoke.tagged_value(report, self.smoke.EXTENSION_DIR_PREFIX),
            "/home/x/Extensions",
        )
        self.assertEqual(
            self.smoke.tagged_value(report, self.smoke.CLASS_FILE_PREFIX),
            "/home/x/Extensions/ChaosOsc/Classes/ChaosOsc.sc",
        )
        self.assertIsNone(self.smoke.tagged_value(report, "MISSING="))

    def test_render_check_accepts_finite_non_silent_float_wav(self):
        scratch = fresh_scratch_dir("wav-ok")
        wav = scratch / "ok.wav"
        frames = [(0.1 * math.sin(i * 0.3),) for i in range(4800)]
        write_float_wav(wav, 1, 48000, frames)

        stats = self.smoke.check_render(wav, expected_channels=1)

        self.assertEqual(stats["sample_rate"], 48000)
        self.assertEqual(stats["channels"], 1)
        self.assertEqual(stats["frames"], 4800)
        self.assertGreater(stats["rms"], 0.05)

    def test_render_check_rejects_silence_and_non_finite_samples(self):
        scratch = fresh_scratch_dir("wav-bad")
        silent = scratch / "silent.wav"
        write_float_wav(silent, 1, 48000, [(0.0,)] * 4800)
        broken = scratch / "nan.wav"
        write_float_wav(broken, 1, 48000, [(0.1,)] * 10 + [(float("nan"),)])

        for path, reason in ((silent, "silent"), (broken, "finite")):
            with self.subTest(path=path.name):
                with self.assertRaises(self.smoke.SmokeTestError) as raised:
                    self.smoke.check_render(path, expected_channels=1)
                self.assertIn(reason, str(raised.exception))

    def test_plugin_paths_are_deduplicated_in_order(self):
        scratch = fresh_scratch_dir("plugin-paths")
        first = scratch / "first"
        second = scratch / "second"
        first.mkdir()
        second.mkdir()

        joined = self.smoke.plugin_path_argument([first, second, first])

        self.assertEqual(
            joined.split(self.smoke.os.pathsep),
            [str(first.resolve()), str(second.resolve())],
        )


class PluginBuildsWorkflowContractTests(unittest.TestCase):
    WORKFLOW = ROOT / ".github" / "workflows" / "plugin-builds.yml"
    SC_WINDOWS_ZIP = (
        "https://github.com/supercollider/supercollider/releases/download/"
        "Version-3.14.1/SuperCollider-3.14.1-win64.zip"
    )
    SC_WINDOWS_ZIP_SHA256 = (
        "a5f95416307d35c039ca53a9f9c6151c26585064d3229521093a60dddb9458cd"
    )

    def read_workflow(self):
        self.assertTrue(self.WORKFLOW.is_file(), "missing {}".format(self.WORKFLOW))
        return self.WORKFLOW.read_text(encoding="utf-8")

    def test_builds_tests_verifies_and_uploads_on_three_platforms(self):
        source = self.read_workflow()
        for expected in (
            "push:",
            "pull_request:",
            "workflow_dispatch:",
            "contents: read",
            "macos-14",
            "ubuntu-latest",
            "windows-latest",
            "-A x64",
            "cmake -S plugin/ChaosOsc",
            "--config Release",
            "ctest --test-dir",
            "cmake --install",
            "scripts/ci_verify_plugin.py",
            "--require-universal",
            "--require-dumpbin",
            "actions/upload-artifact@v4",
            "scripts/install_chaososc.py",
            "--uninstall",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_windows_job_smoke_renders_with_the_pinned_sc_release(self):
        source = self.read_workflow()
        for expected in (
            self.SC_WINDOWS_ZIP,
            self.SC_WINDOWS_ZIP_SHA256,
            "sha256sum --check",
            "scripts/ci_nrt_smoke.py",
            "sclang.exe",
            "scsynth.exe",
            "--expect-user-extension-dir",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)


class QualityCheckCoverageTests(unittest.TestCase):
    def test_quality_checks_syntax_check_the_installer_and_ci_helpers(self):
        source = (ROOT / "scripts" / "run_quality_checks.sh").read_text(
            encoding="utf-8"
        )
        for script in (
            "scripts/install_chaososc.py",
            "scripts/ci_verify_plugin.py",
            "scripts/ci_nrt_smoke.py",
        ):
            with self.subTest(script=script):
                self.assertIn(script, source)


if __name__ == "__main__":
    unittest.main()
