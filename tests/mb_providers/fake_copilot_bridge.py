"""Deterministic process-level stand-in for the Copilot SDK bridge."""
import argparse
import json
from pathlib import Path
import time

parser = argparse.ArgumentParser()
parser.add_argument("--run-dir", required=True)
directory = Path(parser.parse_args().run_dir)
spec = json.loads((directory / "copilot-request.json").read_text(encoding="utf-8"))
if spec["action"] in ("auth", "login"):
    result = {"result": {"authenticated": True}}
elif spec["action"] == "models":
    result = {"result": [{"id": "test-model", "provider": "copilot",
                          "displayName": "Fake Copilot", "usable": True}]}
elif spec["request"]["model"] == "missing":
    result = {"error": {"kind": "unavailableModel", "detail": "Unknown model"}}
else:
    if spec["request"]["model"] == "slow":
        time.sleep(20)
    result = {"result": {"provider": "copilot", "model": spec["request"]["model"],
                         "text": "proposal only", "usage": None}}
(directory / "copilot-response.json").write_text(json.dumps(result), encoding="utf-8")
partial = directory / "exit-code.partial"
partial.write_text("0", encoding="ascii")
partial.replace(directory / "exit-code.txt")
