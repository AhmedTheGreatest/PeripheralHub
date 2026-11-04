"""PeripheralHub Background Monitoring Engine & Cache Manager.

Periodically queries all adapters, caches state atomically to disk,
and triggers notifications when battery thresholds are crossed.
"""

from __future__ import annotations
import os
import json
import time
import signal
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .battery import DeviceState
from .devices.base import BasePeripheralAdapter
from .devices.attack_shark import AttackSharkAdapter
from .devices.aula_f75 import AulaF75Adapter
from .devices.razer_barracuda import RazerBarracudaAdapter
from .notifications import NotificationManager

logger = logging.getLogger("peripheralhub")


def get_cache_dir() -> Path:
    """Return user cache directory for PeripheralHub state."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_dir = base / "peripheralhub"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_file() -> Path:
    return get_cache_dir() / "state.json"


class PeripheralMonitor:
    """Orchestrates hardware adapters, caching, and notification triggers."""

    def __init__(self, adapters: Optional[List[BasePeripheralAdapter]] = None):
        if adapters is None:
            self.adapters: List[BasePeripheralAdapter] = [
                AttackSharkAdapter(),
                AulaF75Adapter(),
                RazerBarracudaAdapter(),
            ]
        else:
            self.adapters = adapters

        self.notifications = NotificationManager()
        self._running = False

    def poll_all(self) -> Dict[str, DeviceState]:
        """Poll all configured peripheral adapters and update cache."""
        states: Dict[str, DeviceState] = {}
        for adapter in self.adapters:
            try:
                state = adapter.poll()
                states[adapter.device_id] = state
                self.notifications.check_and_notify(state)
            except Exception as e:
                logger.error(f"Error polling adapter {adapter.device_id}: {e}")
                states[adapter.device_id] = adapter.get_fallback_state(error=str(e))

        self.save_cache(states)
        return states

    def save_cache(self, states: Dict[str, DeviceState]):
        """Write current states to disk atomically as JSON."""
        cache_file = get_cache_file()
        temp_file = cache_file.with_suffix(".tmp")
        data = {
            "timestamp": time.time(),
            "devices": {dev_id: state.to_dict() for dev_id, state in states.items()},
        }
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, cache_file)
        except Exception as e:
            logger.error(f"Error saving state cache to {cache_file}: {e}")

    @classmethod
    def load_cached_states(cls) -> Optional[Dict[str, DeviceState]]:
        """Load state from disk cache. Returns None if cache does not exist or is invalid."""
        cache_file = get_cache_file()
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            devices_raw = data.get("devices", {})
            return {dev_id: DeviceState.from_dict(d) for dev_id, d in devices_raw.items()}
        except Exception as e:
            logger.debug(f"Error reading cache file {cache_file}: {e}")
            return None

    def run_daemon(self, interval: int = 30):
        """Run continuous monitoring daemon loop."""
        self._running = True
        logger.info(f"PeripheralHub daemon starting with {interval}s polling interval...")

        def _handle_signal(signum, frame):
            logger.info("Termination signal received. Exiting daemon...")
            self._running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        while self._running:
            start_time = time.time()
            try:
                self.poll_all()
            except Exception as e:
                logger.error(f"Daemon polling loop error: {e}")

            elapsed = time.time() - start_time
            sleep_time = max(1.0, interval - elapsed)

            step = 0.5
            waited = 0.0
            while waited < sleep_time and self._running:
                time.sleep(step)
                waited += step

        logger.info("PeripheralHub daemon stopped.")
