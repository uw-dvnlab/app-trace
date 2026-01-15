from typing import Dict, Type, List
from .base import SignalProcessor

_PROCESSORS: Dict[str, Type[SignalProcessor]] = {}

def register_processor(cls: Type[SignalProcessor]):
    """Decorator to register a SignalProcessor class."""
    _PROCESSORS[cls.name] = cls
    return cls

def get_processor(name: str) -> Type[SignalProcessor]:
    """Get a processor class by name."""
    return _PROCESSORS.get(name)

def get_all_processors() -> List[Type[SignalProcessor]]:
    """Get all registered processor classes."""
    return list(_PROCESSORS.values())

def get_processor_names() -> List[str]:
    """Get names of all registered processors."""
    return list(_PROCESSORS.keys())
