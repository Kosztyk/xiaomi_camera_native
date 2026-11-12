"""Dependency-free regression tests for ip029a hardware-verified promotion.

Extract only the pure policy function and data class into an isolated AST
namespace; installing Home Assistant is not required to run these checks.
"""

import ast
import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/xiaomi_camera_native"
VERIFIED = {"chuangmi.camera.029a02", "chuangmi.camera.ip029a", "chuangmi.camera.046c04", "mxiang.camera.c301"}
EXPERIMENTAL = set()


def _policy():
    module = ast.parse((COMP / "protocol/miss.py").read_text())
    wanted = ("PAN_TILT_MODELS", "EXPERIMENTAL_PAN_TILT_MODELS", "PAN_TILT_OPERATIONS")
    nodes = [
        node
        for node in module.body
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in wanted for target in node.targets)
        )
        or (isinstance(node, ast.FunctionDef) and node.name == "pan_tilt_supported")
    ]
    code = compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "miss-policy", "exec")
    namespace = {}
    exec(code, namespace)
    return namespace


class Ip029aTests(unittest.TestCase):
    def test_four_verified_models_and_no_experimental_models(self):
        ns = _policy()
        self.assertEqual(ns["PAN_TILT_MODELS"], VERIFIED)
        self.assertEqual(ns["EXPERIMENTAL_PAN_TILT_MODELS"], EXPERIMENTAL)
        self.assertEqual(ns["PAN_TILT_OPERATIONS"], {"left": 1, "right": 2, "up": 3, "down": 4})

    def test_ip029a_ptz_enabled_even_without_old_opt_in(self):
        allow = _policy()["pan_tilt_supported"]
        for model in VERIFIED:
            for old_switch in (False, True, "true", 1):
                self.assertTrue(allow(model, experimental_enabled=old_switch))
        for model in ("", "random.camera", "chuangmi.camera.ipc019", "chuangmi.camera.039c01"):
            self.assertFalse(allow(model))
            self.assertFalse(allow(model, experimental_enabled=True))

    def test_profile_opt_in_defaults_off_and_persists_boolean(self):
        module = ast.parse((COMP / "protocol/session.py").read_text())
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "StreamOptions")
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        script = compile(ast.fix_missing_locations(ast.Module(body=[future, cls], type_ignores=[])), "stream-options", "exec")
        namespace = {
            "dataclass": dataclass,
            "Any": Any,
            "Mapping": Mapping,
            "parse_h264_height": int,
        }
        exec(script, namespace)
        options = namespace["StreamOptions"]
        self.assertIs(options.from_profile({}).experimental_pan_tilt, False)
        self.assertIs(options.from_profile({"experimental_pan_tilt": True}).experimental_pan_tilt, True)
        self.assertIs(options.from_profile({"experimental_pan_tilt": False}).experimental_pan_tilt, False)

    def test_options_switch_hidden_for_promoted_ip029a(self):
        # The flow includes the field only when the camera model is in the
        # (now empty) experimental allowlist. Existing stored values are harmless.
        flow = (COMP / "config_flow.py").read_text()
        self.assertIn('if device["model"] in EXPERIMENTAL_PAN_TILT_MODELS:', flow)
        self.assertIn('"experimental_pan_tilt", default=current["experimental_pan_tilt"]', flow)
        self.assertNotIn("chuangmi.camera.ip029a", _policy()["EXPERIMENTAL_PAN_TILT_MODELS"])
        session = (COMP / "protocol/session.py").read_text()
        self.assertIn('experimental_enabled=self.options.experimental_pan_tilt', session)
        for p in (COMP / "strings.json", COMP / "translations/en.json"):
            labels = json.loads(p.read_text())
            self.assertIn("experimental_pan_tilt", labels["options"]["step"]["profile"]["data"])

    def test_hardware_verification_report_scope(self):
        report = (ROOT / "docs/PTZ_HARDWARE_VERIFICATION_2026-11-12_ip029a.md").read_text()
        self.assertIn("Home Assistant **2026.11.1**", report)
        self.assertIn("v0.3.11", report)
        self.assertIn("one camera", report.lower())
        self.assertIn("second camera", report.lower())
        self.assertIn("not independently", report.lower())


if __name__ == "__main__":
    unittest.main()
