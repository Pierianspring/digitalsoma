"""DigitalSoma — Digital Twin Framework for Animal Physiology Monitoring."""

__version__ = "1.0.0"

from digitalsoma.soma_api import (
    DigitalSoma,
    SomaConfig,
    build_soma,
    register_animal_type,
    AnatomicalSystem,
)

__all__ = ["DigitalSoma", "SomaConfig", "build_soma", "register_animal_type", "AnatomicalSystem"]
