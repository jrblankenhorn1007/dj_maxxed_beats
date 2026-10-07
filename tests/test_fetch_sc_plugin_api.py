import importlib.util
import io
import ntpath
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import patch


script_path = (
    Path(__file__).resolve().parents[1]
    / "plugin"
    / "fetch_sc_plugin_api.py"
)
spec = importlib.util.spec_from_file_location("fetch_sc_plugin_api", script_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {script_path}")
fetch_sc_plugin_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_sc_plugin_api)


class FetchScPluginApiTests(unittest.TestCase):
    def test_headers_are_pinned_to_the_supported_release(self):
        self.assertEqual(
            fetch_sc_plugin_api.SC_COMMIT,
            "426edf6d8742e1cc3bd85b51ca0c4e595d37a903",
        )

    def test_header_cache_is_scoped_to_the_pinned_revision(self):
        expected = (
            Path(fetch_sc_plugin_api.__file__).resolve().parent
            / ".sc-plugin-api-cache"
            / fetch_sc_plugin_api.SC_COMMIT
        )
        self.assertEqual(Path(fetch_sc_plugin_api.cache_dir()), expected)

    def test_fetch_propagates_network_errors(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(
                fetch_sc_plugin_api.urllib.request,
                "urlopen",
                side_effect=URLError("offline"),
            ), patch.object(fetch_sc_plugin_api.time, "sleep"):
                with self.assertRaises(URLError):
                    fetch_sc_plugin_api.fetch(
                        "include/plugin_interface/SC_PlugIn.hpp",
                        cache_dir,
                    )

    def test_indented_conditional_includes_are_matched(self):
        """Upstream headers sometimes guard an include inside a
        preprocessor conditional, e.g. `#    include "Hash.h"` (whitespace
        between `#` and `include`), not just a bare `#include "X.h"` at
        column 0. INCLUDE_RE must match both forms, or transitively
        included headers referenced this way are silently never fetched."""
        self.assertEqual(
            fetch_sc_plugin_api.INCLUDE_RE.findall('#    include "Hash.h"\n'),
            ["Hash.h"],
        )
        self.assertEqual(
            fetch_sc_plugin_api.INCLUDE_RE.findall('#include "SC_Types.h"\n'),
            ["SC_Types.h"],
        )

    def test_missing_candidate_locations_do_not_abort_resolution(self):
        """SC_PlugIn.hpp's local #include directives are resolved by trying
        each of [its own dir] + SEARCH_DIRS as a candidate directory, and
        only one candidate actually exists upstream per include. A 404 for
        a wrong candidate is an expected, benign outcome, not a fatal
        error -- resolution must keep going and still resolve the entry
        point via whichever candidate does exist."""
        real_content = (
            '#include "SC_Types.h"\n'
            'struct ChaosOsc {};\n'
        )
        real_candidate = "include/common/SC_Types.h"

        def fake_urlopen(url, timeout=20):
            rel = url[len(fetch_sc_plugin_api.BASE_URL):]
            if rel == "include/plugin_interface/SC_PlugIn.hpp":
                return _FakeResponse(real_content.encode("utf-8"))
            if rel == real_candidate:
                return _FakeResponse(b"// real SC_Types.h contents\n")
            # Every other candidate location (e.g. trying SC_Types.h under
            # plugin_interface/ or SC_PlugIn.hpp itself under common/) is a
            # legitimate 404, not a network outage.
            raise HTTPError(url, 404, "Not Found", None, None)

        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(
                fetch_sc_plugin_api.urllib.request,
                "urlopen",
                side_effect=fake_urlopen,
            ):
                resolved = fetch_sc_plugin_api.resolve_headers(cache_dir)

        self.assertIn("include/plugin_interface/SC_PlugIn.hpp", resolved)
        self.assertIn(real_candidate, resolved)
        self.assertNotIn("include/plugin_interface/SC_Types.h", resolved)

    def test_header_urls_use_posix_paths_with_windows_normalization(self):
        """Windows filesystem normalization must not turn raw GitHub URL
        paths into backslash-separated paths, which upstream treats as
        missing candidates."""
        real_candidate = "include/common/SC_Types.h"
        requested_urls = []

        def fake_urlopen(url, timeout=20):
            requested_urls.append(url)
            rel = url[len(fetch_sc_plugin_api.BASE_URL):]
            if rel == "include/plugin_interface/SC_PlugIn.hpp":
                return _FakeResponse(b'#include "SC_Types.h"\n')
            if rel == "include/plugin_interface/SC_PlugIn.h":
                return _FakeResponse(b"")
            if rel == real_candidate:
                return _FakeResponse(b"// real SC_Types.h contents\n")
            raise HTTPError(url, 404, "Not Found", None, None)

        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(
                fetch_sc_plugin_api,
                "os",
                SimpleNamespace(
                    path=ntpath,
                    makedirs=lambda *args, **kwargs: None,
                    getpid=lambda: 1234,
                    replace=lambda source, target: None,
                    remove=lambda path: None,
                ),
            ):
                with patch.object(
                    fetch_sc_plugin_api,
                    "open",
                    new=lambda *args, **kwargs: io.BytesIO(),
                    create=True,
                ):
                    with patch.object(
                        fetch_sc_plugin_api.urllib.request,
                        "urlopen",
                        side_effect=fake_urlopen,
                    ):
                        resolved = fetch_sc_plugin_api.resolve_headers(cache_dir)

        self.assertIn(fetch_sc_plugin_api.BASE_URL + real_candidate, requested_urls)
        self.assertIn(real_candidate, resolved)
        self.assertTrue(all("\\" not in url for url in requested_urls))

    def test_non_404_http_errors_are_not_swallowed(self):
        """A genuine outage (e.g. a 503) while resolving headers must abort
        resolution with that error, never be silently treated the same as
        a missing optional candidate location."""

        def fake_urlopen(url, timeout=20):
            raise HTTPError(url, 503, "Service Unavailable", None, None)

        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(
                fetch_sc_plugin_api.urllib.request,
                "urlopen",
                side_effect=fake_urlopen,
            ), patch.object(fetch_sc_plugin_api.time, "sleep"):
                with self.assertRaises(HTTPError) as ctx:
                    fetch_sc_plugin_api.resolve_headers(cache_dir)
        self.assertEqual(ctx.exception.code, 503)


class FetchRetryTests(unittest.TestCase):
    """Transient failures (timeouts, connection errors, HTTP 429/5xx) are
    retried with exponential backoff; 404 and other 4xx are not."""

    REL = "include/plugin_interface/SC_PlugIn.hpp"

    def run_fetch(self, outcomes):
        calls, sleeps = [], []

        def fake_urlopen(url, timeout=20):
            calls.append(url)
            outcome = outcomes[len(calls) - 1]
            if isinstance(outcome, BaseException):
                raise outcome
            return _FakeResponse(outcome)

        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(fetch_sc_plugin_api.urllib.request, "urlopen", side_effect=fake_urlopen), \
                    patch("sys.stderr", new_callable=io.StringIO):
                try:
                    text = fetch_sc_plugin_api.fetch(self.REL, cache_dir, sleep=sleeps.append)
                    error = None
                except BaseException as caught:  # noqa: B902 - re-checked by callers
                    text, error = None, caught
                written = Path(cache_dir, self.REL)
                files = sorted(p.name for p in written.parent.iterdir()) if written.parent.exists() else []
                content = written.read_bytes() if written.is_file() else None
        return SimpleNamespace(text=text, error=error, calls=len(calls), sleeps=sleeps,
                               files=files, content=content)

    def http(self, code):
        return HTTPError("https://example.invalid", code, "status", None, None)

    def test_timeout_is_retried_with_backoff_then_succeeds(self):
        run = self.run_fetch([TimeoutError("timed out"), URLError("reset"), b"#pragma once\n"])
        self.assertIsNone(run.error)
        self.assertEqual(run.text, "#pragma once\n")
        self.assertEqual(run.calls, 3)
        self.assertEqual(run.sleeps, [1.0, 2.0])
        self.assertEqual(run.files, ["SC_PlugIn.hpp"])

    def test_connection_errors_and_retryable_statuses_are_retried(self):
        for failure in (ConnectionResetError("reset"), self.http(429), self.http(500), self.http(503)):
            with self.subTest(failure=failure):
                run = self.run_fetch([failure, b"ok"])
                self.assertIsNone(run.error)
                self.assertEqual((run.calls, run.sleeps), (2, [1.0]))

    def test_last_error_is_reraised_after_four_attempts(self):
        run = self.run_fetch([self.http(503)] * 4)
        self.assertIsInstance(run.error, HTTPError)
        self.assertEqual(run.error.code, 503)
        self.assertEqual(run.calls, 4)
        self.assertEqual(run.sleeps, [1.0, 2.0, 4.0])
        self.assertEqual(run.files, [])

    def test_timeouts_are_reraised_after_the_last_attempt(self):
        run = self.run_fetch([TimeoutError("timed out")] * 4)
        self.assertIsInstance(run.error, TimeoutError)
        self.assertEqual(run.calls, 4)

    def test_not_found_and_other_client_errors_are_not_retried(self):
        for code in (404, 400, 403):
            with self.subTest(code=code):
                run = self.run_fetch([self.http(code)])
                self.assertIsInstance(run.error, HTTPError)
                self.assertEqual(run.error.code, code)
                self.assertEqual((run.calls, run.sleeps), (1, []))

    def test_write_is_atomic_and_leaves_no_temporary_files(self):
        run = self.run_fetch([b"// header\n"])
        self.assertEqual(run.content, b"// header\n")
        self.assertEqual(run.files, ["SC_PlugIn.hpp"])

    def test_failed_write_leaves_neither_partial_file_nor_temporary(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.object(fetch_sc_plugin_api.urllib.request, "urlopen",
                              return_value=_FakeResponse(b"data")), \
                    patch.object(fetch_sc_plugin_api.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    fetch_sc_plugin_api.fetch(self.REL, cache_dir, sleep=lambda seconds: None)
            folder = Path(cache_dir, self.REL).parent
            self.assertEqual(list(folder.iterdir()), [])


class WorkflowCacheTests(unittest.TestCase):
    def test_every_plugin_building_workflow_caches_the_pinned_headers(self):
        workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for name in ("plugin-builds.yml", "headless-tests.yml", "assistant-tests.yml"):
            with self.subTest(workflow=name):
                source = (workflows / name).read_text(encoding="utf-8")
                self.assertIn("uses: actions/cache@v4", source)
                self.assertIn("path: plugin/.sc-plugin-api-cache", source)
                self.assertIn("${{ runner.os }}", source)
                self.assertIn(fetch_sc_plugin_api.SC_COMMIT, source)


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


if __name__ == "__main__":
    unittest.main()
