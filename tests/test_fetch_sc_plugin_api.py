import importlib.util
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
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


if __name__ == "__main__":
    unittest.main()
