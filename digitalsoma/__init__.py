"""DigitalSoma — Digital Twin Framework for Animal Physiology Monitoring."""

__version__ = "2.2.0"

from digitalsoma.soma_api import (
    DigitalSoma,
    SomaConfig,
    build_soma,
    register_animal_type,
    AnatomicalSystem,
)

from digitalsoma.fhir.fhir_io import (
    to_fhir_bundle,
    from_fhir_bundle,
    FHIRMapper,
)

__all__ = [
    "DigitalSoma", "SomaConfig", "build_soma", "register_animal_type",
    "AnatomicalSystem",
    "to_fhir_bundle", "from_fhir_bundle", "FHIRMapper",
]
