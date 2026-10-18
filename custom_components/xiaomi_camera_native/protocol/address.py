"""Identity-based address recovery, with shared and rate-limited cloud discovery."""

from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import Callable, Iterable
from typing import Any

from .cloud import CameraDevice, XiaomiCloud
from .errors import CloudError

DISCOVERY_INTERVAL = 30
DISCOVERY_TIMEOUT = 10


def camera_address(value: Any) -> str | None:
    """Accept a usable discovered IPv4 address, never a hostname or broadcast."""
    if not isinstance(value, str):
        return None
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return None
    if (
        address.is_unspecified
        or address.is_multicast
        or address.is_loopback
        or address.is_reserved
        or int(address) == 0xFFFFFFFF
    ):
        return None
    return str(address)


def normalized_mac(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.replace(":", "").replace("-", "").replace(".", "").lower()
    if len(value) != 12 or any(char not in "0123456789abcdef" for char in value):
        return None
    return value if value not in {"000000000000", "ffffffffffff"} else None


def router_addresses(device: CameraDevice, states: Iterable[Any]) -> list[str]:
    """Use online router trackers with the exact camera MAC, never a name match."""
    mac = normalized_mac(device.mac)
    if mac is None:
        return []
    addresses = []
    for state in sorted(states, key=lambda item: item.last_updated, reverse=True):
        attrs = state.attributes
        if state.state != "home" or attrs.get("source_type") != "router":
            continue
        if normalized_mac(attrs.get("mac") or attrs.get("mac_address")) != mac:
            continue
        address = camera_address(attrs.get("ip") or attrs.get("ip_address"))
        if address is not None and address not in addresses:
            addresses.append(address)
            # Old duplicate trackers can retain stale addresses. Prefer the
            # most recently updated online router tracker and bound attempts.
            break
    return addresses


class CameraAddressResolver:
    """One resolver per account; healthy connections never need cloud discovery."""

    def __init__(
        self,
        cloud: XiaomiCloud,
        local_lookup: Callable[[CameraDevice], list[str]] | None = None,
    ) -> None:
        self.cloud = cloud
        self.local_lookup = local_lookup or (lambda _device: [])
        self._lock = asyncio.Lock()
        self._next_refresh = 0.0
        self._devices: dict[str, CameraDevice] = {}

    def local_addresses(self, device: CameraDevice) -> list[str]:
        return self.local_lookup(device)

    async def cloud_address(self, device: CameraDevice) -> str | None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            if loop.time() >= self._next_refresh:
                # Throttle failures too. Cancellation propagates and releases
                # the lock, so unloading cannot leave an orphan discovery task.
                self._next_refresh = loop.time() + DISCOVERY_INTERVAL
                self._devices = {}
                try:
                    async with asyncio.timeout(DISCOVERY_TIMEOUT):
                        devices = await self.cloud.devices()
                except asyncio.CancelledError:
                    self._next_refresh = 0
                    raise
                except (CloudError, TimeoutError, OSError):
                    return None
                self._devices = {item.did: item for item in devices}
            discovered = self._devices.get(device.did)
            if discovered is None or discovered.model != device.model:
                return None
            known_mac = normalized_mac(device.mac)
            found_mac = normalized_mac(discovered.mac)
            if known_mac and found_mac and known_mac != found_mac:
                return None
            return camera_address(discovered.host)
