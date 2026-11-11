"""Unit tests for device adapters."""

from src.battery import DeviceState, DeviceType, ChargingStatus
from src.devices.base import BasePeripheralAdapter
from src.devices.attack_shark import AttackSharkAdapter
from src.devices.aula_f75 import AulaF75Adapter
from src.devices.razer_barracuda import RazerBarracudaAdapter


def test_base_adapter_fallback():
    class DummyAdapter(BasePeripheralAdapter):
        def is_receiver_present(self) -> bool:
            return False

        def poll(self) -> DeviceState:
            return self.get_fallback_state(receiver_present=False)

    adapter = DummyAdapter("dummy", "Dummy Device", "Model D", DeviceType.MOUSE)
    state = adapter.poll()
    assert state.device_id == "dummy"
    assert not state.receiver_connected
    assert not state.device_connected
    assert state.battery_percentage is None
    assert state.charging_status == ChargingStatus.UNKNOWN


def test_adapter_instantiation():
    mouse = AttackSharkAdapter()
    assert mouse.device_id == "attack_shark_x11"
    assert mouse.device_type == DeviceType.MOUSE

    kb = AulaF75Adapter()
    assert kb.device_id == "aula_f75"
    assert kb.device_type == DeviceType.KEYBOARD

    headset = RazerBarracudaAdapter()
    assert headset.device_id == "razer_barracuda_x"
    assert headset.device_type == DeviceType.HEADSET


def test_aula_f75_init_parameters():
    kb = AulaF75Adapter(query_interval=300, idle_threshold=30, sleep_threshold=60)
    assert kb.query_interval == 300
    assert kb.idle_threshold == 30
    assert kb.sleep_threshold == 60


def test_aula_f75_idle_skips_rf_query(monkeypatch):
    kb = AulaF75Adapter(query_interval=600, idle_threshold=45)
    kb._cached_battery = 85
    kb._last_reading = 1000.0

    # Mock receiver present
    monkeypatch.setattr(kb, "_find_hidraw_path", lambda interface="INPUT1": ("/dev/dummy", True))
    # Mock activity: not active, not asleep (idle between 45s and 90s)
    monkeypatch.setattr(kb, "_check_activity", lambda: (False, False))

    query_called = False
    def mock_send_query(path):
        nonlocal query_called
        query_called = True
        return 90, True

    monkeypatch.setattr(kb, "_send_query", mock_send_query)

    state = kb.poll(force=False)
    assert not query_called, "RF query should be skipped when keyboard is idle"
    assert state.device_connected is True
    assert state.battery_percentage == 85


def test_aula_f75_sleep_state(monkeypatch):
    kb = AulaF75Adapter(query_interval=600, idle_threshold=45, sleep_threshold=90)
    kb._cached_battery = 85
    kb._last_reading = 1000.0

    monkeypatch.setattr(kb, "_find_hidraw_path", lambda interface="INPUT1": ("/dev/dummy", True))
    # Mock activity: asleep (idle >= 90s)
    monkeypatch.setattr(kb, "_check_activity", lambda: (False, True))

    query_called = False
    monkeypatch.setattr(kb, "_send_query", lambda path: (90, True))

    state = kb.poll(force=False)
    assert state.device_connected is False
    assert state.battery_percentage == 85
    assert "sleeping" in (state.error_message or "").lower()


def test_aula_f75_force_triggers_query(monkeypatch):
    kb = AulaF75Adapter(query_interval=600, idle_threshold=45)
    kb._cached_battery = 85
    kb._last_reading = 1000.0

    monkeypatch.setattr(kb, "_find_hidraw_path", lambda interface="INPUT1": ("/dev/dummy", True))
    # Even if idle:
    monkeypatch.setattr(kb, "_check_activity", lambda: (False, False))

    query_called = False
    def mock_send_query(path):
        nonlocal query_called
        query_called = True
        return 95, True

    monkeypatch.setattr(kb, "_send_query", mock_send_query)

    state = kb.poll(force=True)
    assert query_called, "Force=True must trigger query"
    assert state.battery_percentage == 95
    assert state.device_connected is True

