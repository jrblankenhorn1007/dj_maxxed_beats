import importlib.util
import tempfile
import unittest
from pathlib import Path
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
            ):
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
            ):
                with self.assertRaises(HTTPError) as ctx:
                    fetch_sc_plugin_api.resolve_headers(cache_dir)
        self.assertEqual(ctx.exception.code, 503)


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
