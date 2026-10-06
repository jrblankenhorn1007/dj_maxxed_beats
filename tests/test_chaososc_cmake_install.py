"""Real-toolchain tests for the ChaosOsc CMake project, its install layout,
scripts/install_chaososc.py, and an end-to-end render of the *installed*
plugin with the real SuperCollider 3.14.1 runtime.

Everything is written below tests/.build/chaososc-cmake/ with an isolated
HOME, and every installer run passes --extensions-dir inside that scratch
tree, so the real user Extensions directory is never touched. The module is
skipped only when cmake itself is unavailable; a missing sclang/scsynth makes
the end-to-end test fail, like the other runtime tests.
"""

import filecmp
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE_DIR = ROOT / "plugin" / "ChaosOsc"
FETCH_SCRIPT = ROOT / "plugin" / "fetch_sc_plugin_api.py"
API_CACHE_INCLUDE = (
    ROOT
    / "plugin"
    / ".sc-plugin-api-cache"
    / "426edf6d8742e1cc3bd85b51ca0c4e595d37a903"
    / "include"
)
INSTALLER = ROOT / "scripts" / "install_chaososc.py"
VERIFIER = ROOT / "scripts" / "ci_verify_plugin.py"
NRT_SMOKE = ROOT / "scripts" / "ci_nrt_smoke.py"
WORK_DIR = ROOT / "tests" / ".build" / "chaososc-cmake"
INSTALLER_BUILD_DIR = WORK_DIR / "installer-build"

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
PLUGIN_BINARY = "ChaosOsc" + (".scx" if IS_MACOS or IS_WINDOWS else ".so")
SC_ENTRY_POINTS = {"api_version", "load", "server_type"}
IGNORED_NAMES = {".DS_Store"}

CMAKE = None
CTEST = None


def setUpModule():
    global CMAKE, CTEST
    if shutil.which("cmake") is None:
        raise unittest.SkipTest(
            "cmake is not installed or not on PATH; install CMake >= 3.16 "
            "to run the ChaosOsc CMake build/install tests"
        )
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)
    CMAKE, CTEST = resolve_cmake_binaries()


def resolve_cmake_binaries():
    """Returns the real cmake/ctest binaries. A `cmake` on PATH may be a
    pip console-script wrapper that only imports under the caller's real
    HOME, so the isolated-HOME runs below use the binaries it points at."""
    probe = WORK_DIR / "print_cmake_paths.cmake"
    probe.write_text(
        'message(STATUS "CHAOSOSC_CMAKE=${CMAKE_COMMAND}")\n'
        'message(STATUS "CHAOSOSC_CTEST=${CMAKE_CTEST_COMMAND}")\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        ["cmake", "-P", str(probe)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise AssertionError(
            "cmake is on PATH but failed to run:\n{}\n{}".format(
                result.stdout, result.stderr
            )
        )
    paths = dict(re.findall(r"CHAOSOSC_(CMAKE|CTEST)=(.+)", result.stdout))
    return paths["CMAKE"].strip(), paths["CTEST"].strip()


def isolated_environment(name):
    """A build/runtime environment whose HOME (and Windows LOCALAPPDATA) is
    a scratch directory and which has no inherited CMake defaults or XDG
    overrides, so platform defaults are exercised deterministically."""
    home = WORK_DIR / "home-{}".format(name)
    temp = WORK_DIR / "tmp-{}".format(name)
    home.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    for variable in (
        "CMAKE_BUILD_TYPE",
        "CMAKE_GENERATOR",
        "CMAKE_GENERATOR_PLATFORM",
        "CMAKE_OSX_ARCHITECTURES",
        "MACOSX_DEPLOYMENT_TARGET",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "PATH": os.pathsep.join(
                [str(Path(CMAKE).parent), environment.get("PATH", "")]
            ),
        }
    )
    if IS_WINDOWS:
        environment["USERPROFILE"] = str(home)
        environment["LOCALAPPDATA"] = str(home / "AppData" / "Local")
    return environment


def run(command, environment, cwd=ROOT, timeout=600):
    return subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd),
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_checked(command, environment, cwd=ROOT, timeout=600):
    result = run(command, environment, cwd=cwd, timeout=timeout)
    if result.returncode:
        raise AssertionError(
            "command failed ({}): {}\n{}\n{}".format(
                result.returncode,
                " ".join(str(part) for part in command),
                result.stdout,
                result.stderr,
            )
        )
    return result


def fresh_dir(path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def load_script(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_api_header_cache():
    if not (API_CACHE_INCLUDE / "plugin_interface" / "SC_PlugIn.hpp").is_file():
        run_checked([sys.executable, FETCH_SCRIPT], os.environ.copy(), timeout=300)


def read_cmake_cache(build_dir):
    entries = {}
    cache = build_dir / "CMakeCache.txt"
    for line in cache.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.+-]+):[A-Z]+=(.*)$", line)
        if match:
            entries[match.group(1)] = match.group(2)
    return entries


def relative_files(directory):
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name not in IGNORED_NAMES
    )


def plugin_modules(directory):
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file()
        and "CMakeFiles" not in path.parts
        and path.suffix in {".scx", ".so", ".dylib", ".dll"}
        and "ChaosOsc" in path.name
    )


def global_text_symbols(binary):
    if IS_MACOS:
        command = ["nm", "-gU", str(binary)]
    else:
        command = ["nm", "-g", "--defined-only", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError("nm failed: {}".format(result.stderr))
    symbols = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[-2] == "T":
            symbols.add(fields[-1])
    return symbols


def read_float_wav(path):
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AssertionError("render is not a RIFF/WAVE file")
    chunks = {}
    offset = 12
    while offset + 8 <= len(data):
        name, size = struct.unpack_from("<4sI", data, offset)
        chunks[name] = data[offset + 8 : offset + 8 + size]
        offset += 8 + size + (size & 1)
    fmt = chunks[b"fmt "]
    format_code, channels, sample_rate = struct.unpack_from("<HHI", fmt)
    bits = struct.unpack_from("<H", fmt, 14)[0]
    if format_code == 0xFFFE and len(fmt) >= 40:
        format_code = struct.unpack_from("<I", fmt, 24)[0]
    samples = chunks[b"data"]
    values = struct.unpack("<{}f".format(len(samples) // 4), samples)
    return format_code, channels, sample_rate, bits, values


def resolve_executable(environment_name, executable_name):
    configured = os.environ.get(environment_name)
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise AssertionError(
            "{} does not name an executable file: {}".format(
                environment_name, configured
            )
        )
    resolved = shutil.which(executable_name)
    if resolved:
        return resolved
    raise AssertionError(
        "{} is required (or set {})".format(executable_name, environment_name)
    )


def normalized(path):
    return os.path.normcase(os.path.realpath(str(path)))


class ChaosOscCMakeBuildTests(unittest.TestCase):
    """Configure (no explicit build type), build, ctest, and install the
    standalone plugin/ChaosOsc CMake project exactly as CI does."""

    @classmethod
    def setUpClass(cls):
        cls.environment = isolated_environment("cmake")
        cls.build_dir = fresh_dir(WORK_DIR / "build")
        cls.stage_dir = fresh_dir(WORK_DIR / "stage")
        cls.configure = run_checked(
            [
                CMAKE,
                "-S",
                PLUGIN_SOURCE_DIR,
                "-B",
                cls.build_dir,
                "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            ],
            cls.environment,
        )
        cls.build = run_checked(
            [CMAKE, "--build", cls.build_dir, "--config", "Release", "--parallel"],
            cls.environment,
        )
        cls.ctest = run_checked(
            [CTEST, "-C", "Release", "--output-on-failure"],
            cls.environment,
            cwd=cls.build_dir,
        )
        cls.install = run_checked(
            [
                CMAKE,
                "--install",
                cls.build_dir,
                "--config",
                "Release",
                "--prefix",
                cls.stage_dir,
            ],
            cls.environment,
        )
        cls.cache = read_cmake_cache(cls.build_dir)
        cls.installed = cls.stage_dir / "ChaosOsc"

    def test_defaults_to_release_against_the_pinned_sc_plugin_api(self):
        if "CMAKE_CONFIGURATION_TYPES" not in self.cache:
            self.assertEqual(self.cache.get("CMAKE_BUILD_TYPE"), "Release")
        self.assertIn(
            (API_CACHE_INCLUDE / "plugin_interface").as_posix(),
            self.configure.stdout,
        )
        self.assertIn((API_CACHE_INCLUDE / "common").as_posix(), self.configure.stdout)

    def test_compiles_cxx17_with_warnings_as_errors_and_system_sc_headers(self):
        commands_file = self.build_dir / "compile_commands.json"
        if not commands_file.is_file():
            self.skipTest("generator does not export compile_commands.json")
        commands = {
            Path(entry["file"]).name: entry.get("command")
            or " ".join(entry.get("arguments", []))
            for entry in json.loads(commands_file.read_text(encoding="utf-8"))
        }
        self.assertIn("ChaosOsc.cpp", commands)
        self.assertIn("test_chaos_osc_core.cpp", commands)
        for source, command in commands.items():
            with self.subTest(source=source):
                for flag in ("-Wall", "-Wextra", "-Werror", "-std=c++17"):
                    self.assertIn(flag, command)
        plugin_command = commands["ChaosOsc.cpp"]
        for header_dir in ("plugin_interface", "common"):
            self.assertRegex(
                plugin_command,
                r"-isystem\s+\"?{}".format(
                    re.escape((API_CACHE_INCLUDE / header_dir).as_posix())
                ),
            )

    def test_builds_one_sc_plugin_module_named_for_the_platform(self):
        modules = plugin_modules(self.build_dir)
        self.assertEqual([path.name for path in modules], [PLUGIN_BINARY])

    def test_plugin_exports_the_sc_load_entry_point(self):
        binary = self.installed / PLUGIN_BINARY
        if IS_WINDOWS:
            verifier = load_script(VERIFIER)
            machine, names = verifier.read_pe_exports(binary)
            self.assertEqual(machine, 0x8664)
            self.assertTrue(SC_ENTRY_POINTS.issubset(names), names)
            return
        symbols = global_text_symbols(binary)
        if IS_MACOS:
            # Hidden visibility: only PluginLoad's C entry points escape.
            self.assertEqual(symbols, {"_" + name for name in SC_ENTRY_POINTS})
        else:
            self.assertTrue(SC_ENTRY_POINTS.issubset(symbols), symbols)
            self.assertEqual(
                [name for name in symbols if name.startswith("_Z")], []
            )

    @unittest.skipUnless(IS_MACOS, "universal binaries are macOS-only")
    def test_macos_build_is_universal_for_the_official_sc_app(self):
        self.assertEqual(self.cache.get("CMAKE_OSX_ARCHITECTURES"), "arm64;x86_64")
        self.assertEqual(self.cache.get("CMAKE_OSX_DEPLOYMENT_TARGET"), "11.0")
        binary = self.installed / PLUGIN_BINARY
        lipo = subprocess.run(
            ["lipo", "-info", str(binary)], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(lipo.returncode, 0, lipo.stderr)
        self.assertIn("arm64", lipo.stdout)
        self.assertIn("x86_64", lipo.stdout)
        otool = subprocess.run(
            ["otool", "-l", str(binary)], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(otool.returncode, 0, otool.stderr)
        self.assertEqual(re.findall(r"minos (\S+)", otool.stdout), ["11.0", "11.0"])

    def test_ctest_runs_the_dsp_core_unit_tests(self):
        self.assertIn("chaos_osc_core", self.ctest.stdout)
        self.assertIn("100% tests passed", self.ctest.stdout)

    def test_install_layout_follows_sc_extension_conventions(self):
        self.assertEqual(sorted(p.name for p in self.stage_dir.iterdir()), ["ChaosOsc"])
        self.assertTrue((self.installed / PLUGIN_BINARY).is_file())
        self.assertEqual(
            plugin_modules(self.stage_dir), [self.installed / PLUGIN_BINARY]
        )
        for directory in ("Classes", "HelpSource"):
            with self.subTest(directory=directory):
                source = PLUGIN_SOURCE_DIR / directory
                target = self.installed / directory
                self.assertEqual(relative_files(target), relative_files(source))
                for relative in relative_files(source):
                    self.assertTrue(
                        filecmp.cmp(source / relative, target / relative, shallow=False),
                        relative,
                    )
        for not_installed in ("Source", "Tests", "CMakeLists.txt"):
            self.assertFalse((self.installed / not_installed).exists(), not_installed)

    def test_ci_verifier_accepts_the_staged_install_and_rejects_a_broken_one(self):
        arguments = [sys.executable, VERIFIER, "--staging-dir", self.stage_dir]
        if IS_MACOS:
            arguments.append("--require-universal")
        accepted = run(arguments, self.environment)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn("load", accepted.stdout)

        broken = WORK_DIR / "stage-broken"
        if broken.exists():
            shutil.rmtree(broken)
        shutil.copytree(self.stage_dir, broken)
        shutil.rmtree(broken / "ChaosOsc" / "Classes")
        rejected = run(
            [sys.executable, VERIFIER, "--staging-dir", broken], self.environment
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Classes", rejected.stdout + rejected.stderr)

    def test_sc_path_selects_headers_from_a_supercollider_source_tree(self):
        ensure_api_header_cache()
        sc_root = fresh_dir(WORK_DIR / "fake-sc-root")
        shutil.copytree(API_CACHE_INCLUDE, sc_root / "include")
        build_dir = fresh_dir(WORK_DIR / "build-sc-path")

        configure = run_checked(
            [CMAKE, "-S", PLUGIN_SOURCE_DIR, "-B", build_dir, "-DSC_PATH=" + str(sc_root)],
            self.environment,
        )
        self.assertIn((sc_root / "include" / "plugin_interface").as_posix(), configure.stdout)
        self.assertNotIn("header cache ready", configure.stdout)
        run_checked(
            [CMAKE, "--build", build_dir, "--config", "Release", "--target", "ChaosOsc"],
            self.environment,
        )
        self.assertEqual(
            [path.name for path in plugin_modules(build_dir)], [PLUGIN_BINARY]
        )

        missing = WORK_DIR / "no-such-sc-root"
        rejected = run(
            [
                CMAKE,
                "-S",
                PLUGIN_SOURCE_DIR,
                "-B",
                fresh_dir(WORK_DIR / "build-bad-sc-path"),
                "-DSC_PATH=" + str(missing),
            ],
            self.environment,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("SC_PATH", rejected.stdout + rejected.stderr)
        self.assertIn("SC_PlugIn.hpp", rejected.stdout + rejected.stderr)


class ChaosOscInstallerTests(unittest.TestCase):
    """scripts/install_chaososc.py against scratch Extensions directories."""

    @classmethod
    def setUpClass(cls):
        cls.environment = isolated_environment("installer")
        cls.installer = load_script(INSTALLER)
        cls.marker = cls.installer.MARKER_NAME

    def extensions_dir(self, name):
        path = WORK_DIR / "extensions" / name
        if path.exists():
            shutil.rmtree(path)
        return path

    def run_installer(self, *arguments, environment=None, build_dir=INSTALLER_BUILD_DIR):
        command = [sys.executable, INSTALLER]
        if build_dir is not None:
            command += ["--build-dir", build_dir]
        command += list(arguments)
        return run(command, environment or self.environment)

    def assert_succeeded(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_next_steps(self, output):
        self.assertIn("Recompile Class Library", output)
        self.assertIn("thisProcess.recompile", output)
        self.assertIn("s.reboot", output)

    def assert_installed(self, target):
        self.assertTrue((target / PLUGIN_BINARY).is_file())
        self.assertTrue((target / self.marker).is_file())
        for directory in ("Classes", "HelpSource"):
            self.assertEqual(
                relative_files(target / directory),
                relative_files(PLUGIN_SOURCE_DIR / directory),
            )

    def make_foreign_folder(self, extensions):
        foreign = extensions / "ChaosOsc" / "Classes" / "Foreign.sc"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("// not installed by the ChaosOsc installer\n", encoding="utf-8")
        return foreign

    def test_install_creates_a_marked_extension_and_prints_next_steps(self):
        extensions = self.extensions_dir("fresh")

        result = self.run_installer("--extensions-dir", extensions)

        self.assert_succeeded(result)
        self.assert_installed(extensions / "ChaosOsc")
        self.assert_next_steps(result.stdout)
        self.assertIn(str(extensions / "ChaosOsc"), result.stdout)

    def test_reinstall_replaces_a_marked_install_without_force(self):
        extensions = self.extensions_dir("reinstall")
        self.assert_succeeded(self.run_installer("--extensions-dir", extensions))
        stale = extensions / "ChaosOsc" / "Classes" / "Stale.sc"
        stale.write_text("// stale file from an older install\n", encoding="utf-8")

        result = self.run_installer("--extensions-dir", extensions)

        self.assert_succeeded(result)
        self.assertFalse(stale.exists(), "reinstall kept a stale file")
        self.assert_installed(extensions / "ChaosOsc")

    def test_refuses_to_overwrite_an_unmarked_folder_before_building(self):
        extensions = self.extensions_dir("unmarked")
        foreign = self.make_foreign_folder(extensions)
        unused_build_dir = WORK_DIR / "installer-build-never-created"

        result = self.run_installer(
            "--extensions-dir", extensions, build_dir=unused_build_dir
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--force", result.stderr)
        self.assertTrue(foreign.is_file(), "an unmarked folder was modified")
        self.assertFalse(unused_build_dir.exists(), "refusal happened after building")

    def test_force_replaces_an_unmarked_folder(self):
        extensions = self.extensions_dir("forced")
        foreign = self.make_foreign_folder(extensions)

        result = self.run_installer("--extensions-dir", extensions, "--force")

        self.assert_succeeded(result)
        self.assertFalse(foreign.exists())
        self.assert_installed(extensions / "ChaosOsc")

    def test_uninstall_removes_only_marked_installs(self):
        extensions = self.extensions_dir("uninstall")
        nothing = self.run_installer("--extensions-dir", extensions, "--uninstall")
        self.assert_succeeded(nothing)
        self.assertIn("nothing to uninstall", nothing.stdout.lower())

        foreign = self.make_foreign_folder(extensions)
        for extra in ([], ["--force"]):
            with self.subTest(extra=extra):
                refused = self.run_installer(
                    "--extensions-dir", extensions, "--uninstall", *extra
                )
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn(self.marker, refused.stderr)
                self.assertTrue(foreign.is_file())

        shutil.rmtree(extensions / "ChaosOsc")
        self.assert_succeeded(self.run_installer("--extensions-dir", extensions))
        removed = self.run_installer("--extensions-dir", extensions, "--uninstall")
        self.assert_succeeded(removed)
        self.assertFalse((extensions / "ChaosOsc").exists())
        self.assertTrue(extensions.is_dir(), "uninstall removed the Extensions dir")
        self.assert_next_steps(removed.stdout)

    def test_dry_run_reports_the_plan_without_side_effects(self):
        extensions = self.extensions_dir("dry-run")
        build_dir = WORK_DIR / "installer-build-dry-run"

        planned = self.run_installer(
            "--extensions-dir", extensions, "--dry-run", build_dir=build_dir
        )

        self.assert_succeeded(planned)
        for expected in ("-S", "--build", "--install", "--prefix", "Release"):
            self.assertIn(expected, planned.stdout)
        self.assertIn(str(extensions / "ChaosOsc"), planned.stdout)
        self.assertIn("dry run", planned.stdout.lower())
        self.assertFalse(build_dir.exists())
        self.assertFalse(extensions.exists())

        foreign = self.make_foreign_folder(extensions)
        refused = self.run_installer(
            "--extensions-dir", extensions, "--dry-run", build_dir=build_dir
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--force", refused.stderr)
        self.assertTrue(foreign.is_file())

        (extensions / "ChaosOsc" / self.marker).write_text("marked\n", encoding="utf-8")
        uninstall_plan = self.run_installer(
            "--extensions-dir", extensions, "--uninstall", "--dry-run"
        )
        self.assert_succeeded(uninstall_plan)
        self.assertIn(str(extensions / "ChaosOsc"), uninstall_plan.stdout)
        self.assertTrue(foreign.is_file(), "dry-run uninstall removed files")
        self.assertFalse(build_dir.exists())

    def test_missing_cmake_is_reported_with_install_hints(self):
        extensions = self.extensions_dir("no-cmake")
        empty_path = fresh_dir(WORK_DIR / "empty-path")
        environment = dict(self.environment, PATH=str(empty_path))
        build_dir = WORK_DIR / "installer-build-no-cmake"

        result = self.run_installer(
            "--extensions-dir", extensions, environment=environment, build_dir=build_dir
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CMake", result.stderr)
        self.assertIn("3.16", result.stderr)
        self.assertFalse(build_dir.exists())
        self.assertFalse(extensions.exists())

    def test_invalid_sc_path_is_rejected_before_configuring(self):
        extensions = self.extensions_dir("bad-sc-path")
        build_dir = WORK_DIR / "installer-build-bad-sc-path"

        result = self.run_installer(
            "--extensions-dir",
            extensions,
            "--sc-path",
            WORK_DIR / "no-such-sc-root",
            build_dir=build_dir,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--sc-path", result.stderr)
        self.assertIn("SC_PlugIn.hpp", result.stderr)
        self.assertFalse(build_dir.exists())

    def test_build_failure_is_reported_actionably_and_installs_nothing(self):
        ensure_api_header_cache()
        broken_sc = fresh_dir(WORK_DIR / "broken-sc-root")
        shutil.copytree(API_CACHE_INCLUDE, broken_sc / "include")
        (broken_sc / "include" / "plugin_interface" / "SC_PlugIn.hpp").write_text(
            '#error "deliberately broken header for the installer failure test"\n',
            encoding="utf-8",
        )
        extensions = self.extensions_dir("build-failure")

        result = self.run_installer(
            "--extensions-dir",
            extensions,
            "--sc-path",
            broken_sc,
            build_dir=WORK_DIR / "installer-build-broken",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("build failed", result.stderr.lower())
        self.assertIn("deliberately broken header", result.stdout + result.stderr)
        self.assertFalse((extensions / "ChaosOsc").exists())


class ChaosOscInstalledRuntimeEndToEndTests(unittest.TestCase):
    """Install into the platform Extensions folder of a scratch HOME, then
    prove sclang compiles the class from there (no --include-path) and
    scsynth renders it from the installed plugin directory in NRT mode."""

    def test_installed_plugin_compiles_in_sclang_and_renders_in_scsynth(self):
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        environment = isolated_environment("e2e")
        home = Path(environment["HOME"])
        installer = load_script(INSTALLER)
        extensions = Path(installer.default_extensions_dir(sys.platform, environment))
        self.assertTrue(
            normalized(extensions).startswith(normalized(home) + os.sep),
            "refusing to install outside the scratch HOME: {}".format(extensions),
        )
        if IS_MACOS:
            self.assertEqual(
                extensions,
                home / "Library" / "Application Support" / "SuperCollider" / "Extensions",
            )
        installed = extensions / "ChaosOsc"

        install = run(
            [
                sys.executable,
                INSTALLER,
                "--extensions-dir",
                extensions,
                "--build-dir",
                INSTALLER_BUILD_DIR,
            ],
            environment,
        )
        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)

        report_path = WORK_DIR / "e2e-report.json"
        smoke_command = [
            sys.executable,
            NRT_SMOKE,
            "--sclang",
            sclang,
            "--scsynth",
            scsynth,
            "--plugin-dir",
            installed,
            "--work-dir",
            fresh_dir(WORK_DIR / "e2e-nrt"),
            "--expect-user-extension-dir",
            extensions,
            "--report",
            report_path,
        ]
        for builtin in filter(
            None, os.environ.get("SC_DEFAULT_PLUGIN_PATH", "").split(os.pathsep)
        ):
            smoke_command += ["--builtin-plugins", builtin]
        smoke = run(smoke_command, environment)
        self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertNotIn("--include-path", report["sclang_command"])
        self.assertEqual(normalized(report["user_extension_dir"]), normalized(extensions))
        self.assertTrue(
            normalized(report["class_file"]).startswith(
                normalized(installed / "Classes") + os.sep
            ),
            report["class_file"],
        )
        scsynth_command = report["scsynth_command"]
        for expected in ("-N", "WAV", "float"):
            self.assertIn(expected, scsynth_command)
        self.assertEqual(
            scsynth_command[scsynth_command.index("-D") + 1], "0"
        )
        plugin_paths = scsynth_command[scsynth_command.index("-U") + 1].split(os.pathsep)
        self.assertEqual(normalized(plugin_paths[0]), normalized(installed))
        self.assertGreaterEqual(len(plugin_paths), 2, "built-in plugins missing")
        self.assertEqual(len(plugin_paths), len(set(map(normalized, plugin_paths))))

        format_code, channels, sample_rate, bits, samples = read_float_wav(
            report["render"]
        )
        self.assertEqual((format_code, bits), (3, 32))
        self.assertEqual(channels, 1)
        self.assertEqual(sample_rate, 48000)
        self.assertGreater(len(samples), sample_rate // 4)
        self.assertTrue(all(math.isfinite(sample) for sample in samples))
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        self.assertGreater(rms, 0.005, "installed ChaosOsc rendered silence")

    def test_smoke_helper_fails_fast_when_the_class_is_not_installed(self):
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        environment = isolated_environment("e2e-not-installed")
        empty_plugin_dir = fresh_dir(WORK_DIR / "not-installed" / "ChaosOsc")

        result = run(
            [
                sys.executable,
                NRT_SMOKE,
                "--sclang",
                sclang,
                "--scsynth",
                scsynth,
                "--plugin-dir",
                empty_plugin_dir,
                "--work-dir",
                fresh_dir(WORK_DIR / "not-installed-nrt"),
                "--timeout",
                "120",
            ],
            environment,
            timeout=180,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not compile the ChaosOsc class", result.stderr)
        self.assertNotIn("timed out", result.stderr)


if __name__ == "__main__":
    unittest.main()
