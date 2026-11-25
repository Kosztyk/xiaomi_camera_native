"""Offline regression checks for the private ipc020 horizontal-pan-only test.

Keep the existing four-direction MISS controls, verify ipc020 cannot emit a
vertical motor write, and remove only obsolete same-entry tilt registry rows.
"""
from __future__ import annotations

import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_ip029a import MI_360_2K_PRO, VERIFIED, _policy
from test_ipc020_tutk_transport import load_protocol

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/xiaomi_camera_native"
IPC020 = "chuangmi.camera.ipc020"
IP029A = "chuangmi.camera.ip029a"
DOMAIN = "xiaomi_camera_native"


def isolated_code(filename: str, cls: str | None, methods: tuple[str, ...], env: dict):
    tree = ast.parse((COMP / filename).read_text())
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    if cls:
        source = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == cls)
        selected = [item for item in source.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in methods]
        body = [ast.ClassDef(name="TestPolicy", bases=[], keywords=[], body=selected, decorator_list=[])]
    else:
        selected = [item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in methods]
        body = selected
    if len(selected) != len(methods):
        raise AssertionError(f"Missing tested methods in {filename}")
    ns = dict(env)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, *body], type_ignores=[])), filename, "exec"), ns)
    return ns["TestPolicy" if cls else methods[0]]


class DirectionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Policy = isolated_code(
            "protocol/session.py", "CameraSession",
            ("_uses_legacy_tutk", "supported_pan_tilt_directions", "supports_pan_tilt"),
            {"pan_tilt_supported": _policy()["pan_tilt_supported"]},
        )

    def policy(self, model, legacy=False, motor=False):
        obj = self.Policy()
        obj.device = SimpleNamespace(model=model, did="TEST")
        obj.options = SimpleNamespace(experimental_legacy_tutk=legacy, experimental_pan_tilt=motor)
        return obj

    def test_ipc020_only_left_right_when_both_test_options_enabled(self):
        p = self.policy(IPC020, legacy=True, motor=True)
        self.assertEqual(p.supported_pan_tilt_directions, ("left", "right"))
        self.assertTrue(p.supports_pan_tilt)

    def test_ipc020_opt_in_required_and_saved_legacy_profiles_safe(self):
        for legacy, motor in ((False, False), (True, False), (False, True)):
            p = self.policy(IPC020, legacy=legacy, motor=motor)
            self.assertEqual(p.supported_pan_tilt_directions, ())
            self.assertFalse(p.supports_pan_tilt)

    def test_verified_cs2_models_retain_all_four_buttons(self):
        for model in sorted(VERIFIED):
            p = self.policy(model)
            self.assertEqual(p.supported_pan_tilt_directions, ("left", "right", "up", "down"))

    def test_unknown_model_never_gets_controls(self):
        self.assertEqual(self.policy("unknown.camera.X", legacy=True, motor=True).supported_pan_tilt_directions, ())


class ButtonSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_supported_button_entities_are_created(self):
        setup = isolated_code("button.py", None, ("async_setup_entry",),
            {"XiaomiPanTiltButton": lambda session, description: (session.device.model, description.key),
             "BUTTONS": [SimpleNamespace(key=k) for k in ("left", "right", "up", "down")]})
        cameras = [SimpleNamespace(device=SimpleNamespace(model=IPC020), supports_pan_tilt=True,
                                   supported_pan_tilt_directions=("left", "right")),
                   SimpleNamespace(device=SimpleNamespace(model=IP029A), supports_pan_tilt=True,
                                   supported_pan_tilt_directions=("left", "right", "up", "down")),
                   SimpleNamespace(device=SimpleNamespace(model=MI_360_2K_PRO), supports_pan_tilt=True,
                                   supported_pan_tilt_directions=("left", "right", "up", "down")),
                   SimpleNamespace(device=SimpleNamespace(model="other"), supports_pan_tilt=False,
                                   supported_pan_tilt_directions=())]
        entry = SimpleNamespace(runtime_data=SimpleNamespace(sessions={i: cam for i, cam in enumerate(cameras)}))
        created = []
        await setup(None, entry, lambda items: created.extend(items))
        self.assertEqual(created[:2], [(IPC020, "left"), (IPC020, "right")])
        self.assertEqual(created[2:], [
            (model, key)
            for model in (IP029A, MI_360_2K_PRO)
            for key in ("left", "right", "up", "down")
        ])


class RegistryCleanupTests(unittest.TestCase):
    @staticmethod
    def run_cleanup(sessions, entries):
        class Registry:
            def __init__(self):
                self.entries = {ent.entity_id: ent for ent in entries}
                self.removed = []
            def async_get_entity_id(self, domain, platform, unique_id):
                for entity in self.entries.values():
                    if entity.platform == platform and entity.unique_id == unique_id:
                        return entity.entity_id
                return None
            def async_get(self, entity_id):
                return self.entries.get(entity_id)
            def async_remove(self, entity_id):
                self.removed.append(entity_id)
                self.entries.pop(entity_id)
        registry = Registry()
        class ER:
            @staticmethod
            def async_get(_hass):
                return registry
        namespace = {"er": ER, "DOMAIN": DOMAIN,
                     "_LOGGER": SimpleNamespace(debug=lambda *_args: None)}
        cleanup = isolated_code("__init__.py", None, ("_cleanup_unsupported_ipc020_tilt_entities",), namespace)
        entry = SimpleNamespace(entry_id="owner_a",runtime_data=SimpleNamespace(sessions=sessions))
        cleanup(None, entry)
        removed_once = registry.removed[:]
        cleanup(None, entry)
        return registry, removed_once

    def test_only_orphaned_ipc020_up_down_deleted(self):
        sessions = {
            "ipc": SimpleNamespace(device=SimpleNamespace(model=IPC020,did="ipc")),
            "modern": SimpleNamespace(device=SimpleNamespace(model=IP029A,did="modern")),
        }
        entries = [SimpleNamespace(entity_id=f"button.{did}_{direction}",
                                   unique_id=f"{did}_ptz_{direction}",platform=DOMAIN,
                                   config_entry_id="owner_a")
                   for did in ("ipc", "modern") for direction in ("left", "right", "up", "down")]
        registry, removed_once = self.run_cleanup(sessions, entries)
        self.assertCountEqual(removed_once, ["button.ipc_up", "button.ipc_down"])
        self.assertEqual(registry.removed, removed_once, "Reconciliation must be idempotent")
        self.assertIn("button.ipc_left", registry.entries)
        self.assertIn("button.ipc_right", registry.entries)
        self.assertIn("button.modern_up", registry.entries)
        self.assertIn("button.modern_down", registry.entries)

    def test_foreign_config_entry_registry_rows_are_protected(self):
        sessions = {"ipc": SimpleNamespace(device=SimpleNamespace(model=IPC020,did="ipc"))}
        row = SimpleNamespace(entity_id="button.shared_tilt", unique_id="ipc_ptz_up",
                              platform=DOMAIN, config_entry_id="owner_b")
        registry, removed_once = self.run_cleanup(sessions, [row])
        self.assertEqual(removed_once, [])
        self.assertIn(row.entity_id, registry.entries)

    def test_unselected_ipc020_is_not_purged_by_capability_cleanup(self):
        sessions = {"modern": SimpleNamespace(device=SimpleNamespace(model=IP029A,did="modern"))}
        row = SimpleNamespace(entity_id="button.old_ipc_up",unique_id="ipc_ptz_up",
                              platform=DOMAIN,config_entry_id="owner_a")
        registry, removed_once = self.run_cleanup(sessions, [row])
        self.assertEqual(removed_once, [])
        self.assertIn(row.entity_id,registry.entries)


class SendGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_rejects_tilt_without_writing_motor_command(self):
        mod = load_protocol()
        provisioning = SimpleNamespace(uid="FAKE", auth_mode="password", password="FAKE", private=b"",public=b"",device_public=b"",sign="")
        client = mod.TutkClient("192.0.2.4", provisioning, None)
        client._started = True
        client.status.video_packets = 10
        client._send_control = AsyncMock()
        for direction in ("up", "down"):
            with self.assertRaises(mod.ProtocolError):
                await client.pan_tilt(direction)
        client._send_control.assert_not_called()

    async def test_session_rejects_tilt_before_any_connection_work(self):
        mod = load_protocol()
        p = SimpleNamespace(supported_pan_tilt_directions=("left", "right"))
        method = isolated_code("protocol/session.py", "CameraSession", ("pan_tilt",),
                               {"PAN_TILT_OPERATIONS": {"left":1,"right":2,"up":3,"down":4},
                                "ProtocolError": mod.ProtocolError})
        for direction in ("up", "down"):
            with self.assertRaises(mod.ProtocolError):
                await method.pan_tilt(p,direction)


class FrontendTests(unittest.TestCase):
    def test_popup_hides_unsupported_arrows_not_just_disables_them(self):
        body = (COMP / "frontend/camera-controls.js").read_text()
        self.assertIn("button.hidden = !supported", body)
        self.assertIn("button[hidden] { display: none; }", body)
        self.assertIn("this._targets?.[direction]", body)
        self.assertIn("const supported = typeof target ===", body)

    def test_capability_list_exposed_without_sensitive_details(self):
        for filename in ("camera.py", "diagnostics.py"):
            body = (COMP / filename).read_text()
            self.assertIn('"pan_tilt_directions": list(session.supported_pan_tilt_directions)',body)
            self.assertNotIn("provision.uid", body)
            self.assertNotIn("provision.password", body)


if __name__ == "__main__":
    unittest.main()
