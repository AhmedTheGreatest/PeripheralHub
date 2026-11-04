"""Device adapters for PeripheralHub."""

from .base import BasePeripheralAdapter
from .attack_shark import AttackSharkAdapter
from .aula_f75 import AulaF75Adapter
from .razer_barracuda import RazerBarracudaAdapter

__all__ = [
    "BasePeripheralAdapter",
    "AttackSharkAdapter",
    "AulaF75Adapter",
    "RazerBarracudaAdapter",
]
