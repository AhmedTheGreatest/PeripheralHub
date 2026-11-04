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
