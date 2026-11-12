"""Dependency-free lifecycle tests: exercise real functions with fake HA registries."""

import ast
import asyncio
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/xiaomi_camera_native/__init__.py"
DOMAIN = "xiaomi_camera_native"


@dataclass
class FakeDevice:
    id: str
    did: str
    config_entries: frozenset[str]
    domain: str = DOMAIN

    @property
    def identifiers(self):
        return {(self.domain, self.did)}


@dataclass
class FakeEntity:
    entity_id: str
    device_id: str
    config_entry_id: str
    platform: str = DOMAIN


class FakeDevices:
    def __init__(self, devices):
        self.devices = {d.id: d for d in devices}
        self.removed = []

    def async_get(self, device_id):
        return self.devices.get(device_id)

    def async_remove_device(self, device_id):
        self.removed.append(device_id)
        del self.devices[device_id]


class FakeEntities:
    def __init__(self, entities):
        self.entities = {e.entity_id: e for e in entities}
        self.removed = []

    def async_remove(self, entity_id):
        self.removed.append(entity_id)
        del self.entities[entity_id]


class FakeDR:
    @staticmethod
    def async_get(hass):
        return hass.devices

    @staticmethod
    def async_entries_for_config_entry(registry, entry_id):
        return [
            d for d in registry.devices.values() if entry_id in d.config_entries
        ]


class FakeER:
    @staticmethod
    def async_get(hass):
        return hass.entities

    @staticmethod
    def async_entries_for_device(registry, device_id, include_disabled_entities=False):
        assert include_disabled_entities
        return [
            e for e in registry.entities.values() if e.device_id == device_id
        ]


def load_policy():
    tree = ast.parse(SOURCE.read_text())
    names = {
        "_configured_camera_ids",
        "_is_removed_camera_device",
        "_remove_camera_entities",
        "_cleanup_removed_camera_devices",
        "async_remove_config_entry_device",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names
    ]
    assert len(nodes) == len(names)
    script = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            *nodes,
        ],
        type_ignores=[],
    )
    namespace = {
        "CONF_DEVICES": "devices",
        "DOMAIN": DOMAIN,
        "dr": FakeDR,
        "er": FakeER,
        "_LOGGER": SimpleNamespace(debug=lambda *args: None),
    }
    exec(compile(ast.fix_missing_locations(script), str(SOURCE), "exec"), namespace)
    return namespace


def make_env(selected=("keep",)):
    entry = SimpleNamespace(
        entry_id="account-a", data={"devices": [{"did": did} for did in selected]}
    )
    devices = FakeDevices(
        [
            FakeDevice("dev-keep", "keep", frozenset({"account-a"})),
            FakeDevice("dev-garage", "removed", frozenset({"account-a"})),
            FakeDevice("dev-foreign", "unrelated", frozenset({"account-b"})),
            FakeDevice("dev-shared", "shared", frozenset({"account-a", "account-b"})),
            FakeDevice("dev-other-platform", "foreign", frozenset({"account-a"}), "other_integration"),
        ]
    )
    entities = FakeEntities(
        [
            FakeEntity("camera.keep", "dev-keep", "account-a"),
            FakeEntity("camera.garage", "dev-garage", "account-a"),
            FakeEntity("button.garage_left", "dev-garage", "account-a"),
            FakeEntity("button.garage_right", "dev-garage", "account-a"),
            FakeEntity("sensor.foreign", "dev-garage", "account-b", "other_integration"),
            FakeEntity("camera.foreign", "dev-foreign", "account-b"),
        ]
    )
    return SimpleNamespace(devices=devices, entities=entities), entry


class DeviceCleanupTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.hass, self.entry = make_env()

    def test_rediscover_prunes_orphans_and_ptz_entities(self):
        self.policy["_cleanup_removed_camera_devices"](self.hass, self.entry)
        self.assertEqual(self.hass.devices.removed, ["dev-garage"])
        self.assertEqual(
            set(self.hass.entities.removed),
            {"camera.garage", "button.garage_left", "button.garage_right"},
        )
        self.assertIn("sensor.foreign", self.hass.entities.entities)
        self.assertIn("camera.keep", self.hass.entities.entities)

    def test_active_devices_and_other_entry_devices_are_untouched(self):
        self.policy["_cleanup_removed_camera_devices"](self.hass, self.entry)
        self.assertIn("dev-keep", self.hass.devices.devices)
        self.assertIn("dev-foreign", self.hass.devices.devices)
        self.assertIn("dev-other-platform", self.hass.devices.devices)
        self.assertIn("dev-shared", self.hass.devices.devices)

    def test_repeat_cleanup_is_idempotent(self):
        cleanup = self.policy["_cleanup_removed_camera_devices"]
        cleanup(self.hass, self.entry)
        cleanup(self.hass, self.entry)
        self.assertEqual(self.hass.devices.removed, ["dev-garage"])

    def test_ui_delete_only_allows_old_orphan(self):
        delete = self.policy["async_remove_config_entry_device"]
        self.assertFalse(
            asyncio.run(delete(self.hass, self.entry, self.hass.devices.async_get("dev-keep")))
        )
        self.assertFalse(
            asyncio.run(delete(self.hass, self.entry, self.hass.devices.async_get("dev-shared")))
        )
        self.assertFalse(
            asyncio.run(delete(self.hass, self.entry, self.hass.devices.async_get("dev-foreign")))
        )
        self.assertTrue(
            asyncio.run(delete(self.hass, self.entry, self.hass.devices.async_get("dev-garage")))
        )
        self.assertEqual(self.hass.devices.removed, [])  # HA core deletes after true
        self.assertNotIn("camera.garage", self.hass.entities.entities)

    def test_deselected_camera_eligible_after_new_config_load(self):
        old_device = self.hass.devices.async_get("dev-keep")
        self.entry.data["devices"] = [{"did": "new"}]
        self.assertTrue(self.policy["_is_removed_camera_device"](self.entry, old_device))

    def test_reconcile_wired_after_successful_entity_setup(self):
        code = SOURCE.read_text()
        self.assertIn("await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n        # Only reconcile", code)
        flow = (ROOT / "custom_components/xiaomi_camera_native/config_flow.py").read_text()
        self.assertIn("if did in selected", flow)
        self.assertIn("CONF_PROFILES: {", flow)


if __name__ == "__main__":
    unittest.main()
