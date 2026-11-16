"""Offline tests of ipc020 probe classification; no network or credentials."""
from __future__ import annotations

import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "custom_components/xiaomi_camera_native"


def get_probe():
    module = ast.parse((COMP / "protocol/cloud.py").read_text())
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "XiaomiCloud")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "probe_ipc020_legacy")
    ns = {"CameraDevice": SimpleNamespace, "generate_keypair": lambda: (bytes.fromhex("ab"*32), bytes.fromhex("cd"*32))}
    class CloudError(Exception):
        def __init__(self, message, *, code=None):
            super().__init__(message); self.code=code
    class AuthenticationError(Exception):
        pass
    ns.update(CloudError=CloudError, AuthenticationError=AuthenticationError)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), "probe", "exec"),ns)
    return ns["probe_ipc020_legacy"],CloudError,AuthenticationError


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_credentials_with_password(self):
        probe,_,_=get_probe()
        class Cloud:
            async def request(self,path,params,*,retry):
                self.asserts=(path,params,retry)
                return {"p2p_id":"SECRET_UID","password":"SECRET_PASSWORD"}
        cloud=Cloud()
        result=await probe(cloud,SimpleNamespace(model="chuangmi.camera.ipc020",did="1234"))
        self.assertEqual(result,"legacy_p2p_credentials_available")
        self.assertEqual(cloud.asserts,("/device/devicepass",{"did":"1234","toSignAppData":"ab"*32},False))
        self.assertNotIn("SECRET",result)

    async def test_legacy_credentials_with_signed_exchange(self):
        probe,_,_=get_probe()
        class Cloud:
            async def request(self,*a,**kw):
                return {"p2p_id":"SECRET_UID","signForAppData":"SECRET_SIGN","p2p_dev_public_key":"SECRET_KEY"}
        self.assertEqual(await probe(Cloud(),SimpleNamespace(model="chuangmi.camera.ipc020",did="2")),"legacy_p2p_credentials_available")

    async def test_incomplete_and_missing_credentials(self):
        probe,_,_=get_probe()
        for response,expected in (({},"legacy_no_p2p_id"),
                                  ({"p2p_id":"SECRET"},"legacy_incomplete_credentials"),
                                  ([],"legacy_invalid_result")):
            class Cloud:
                async def request(self,*a,**kw): return response
            self.assertEqual(await probe(Cloud(),SimpleNamespace(model="chuangmi.camera.ipc020",did="2")),expected)

    async def test_cloud_rejection_is_sanitized(self):
        probe,CloudError,_=get_probe()
        class Cloud:
            async def request(self,*a,**kw): raise CloudError("private server message",code=-6)
        self.assertEqual(await probe(Cloud(),SimpleNamespace(model="chuangmi.camera.ipc020",did="2")),"legacy_cloud_code_-6")

    async def test_reject_other_models_before_network(self):
        probe,_,_=get_probe()
        class Cloud:
            async def request(self,*a,**kw): raise AssertionError("network call")
        with self.assertRaises(ValueError):
            await probe(Cloud(),SimpleNamespace(model="chuangmi.camera.ip029a",did="2"))

    def test_integration_probe_only_after_negative_six_and_once(self):
        s=(COMP/"protocol/session.py").read_text()
        self.assertIn('self.device.model == "chuangmi.camera.ipc020"',s)
        self.assertIn('err.code == -6',s)
        self.assertIn('and not self._legacy_probe_done',s)
        self.assertIn('self._legacy_probe_done = True',s)
        self.assertIn('attributes["ipc020_legacy_probe"] = session.legacy_probe_status', (COMP / "camera.py").read_text())
        self.assertIn('"ipc020_legacy_probe": session.legacy_probe_status', (COMP / "diagnostics.py").read_text())
        self.assertIn('EXPERIMENTAL_PAN_TILT_MODELS = frozenset({"chuangmi.camera.ipc020"})', (COMP/"protocol/miss.py").read_text())


if __name__ == "__main__":
    unittest.main()
