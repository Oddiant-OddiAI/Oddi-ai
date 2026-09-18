from dataclasses import dataclass
from typing import Dict, Any

from config.platform import PLATFORM_CONFIG
from identity.identity import Identity


@dataclass(frozen=True)
class RuntimeContext:
    platform: str
    application: str
    environment: str
    version: str
    identity: Identity
    capabilities: Dict[str, Any]


def create_runtime_context(
    identity: Identity,
    capabilities: Dict[str, Any],
) -> RuntimeContext:

    return RuntimeContext(
        platform=PLATFORM_CONFIG["name"],
        application=PLATFORM_CONFIG["application"],
        environment=PLATFORM_CONFIG["environment"],
        version=PLATFORM_CONFIG["version"],
        identity=identity,
        capabilities=capabilities,
    )