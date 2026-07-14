from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Port:
    name: str
    direction: str = ""
    data_type: str = ""
    packed: str = ""
    unpacked: str = ""
    interface_type: tuple[str, ...] = ()


@dataclass(frozen=True)
class Param:
    name: str
    value: str = ""
    data_type: str = ""
    packed: str = ""
    unpacked: str = ""
    kind: str = "parameter"


@dataclass(frozen=True)
class Instance:
    module: str
    name: str
    start: int
    end: int
    port_open: int
    port_close: int
    param_open: int | None = None
    param_close: int | None = None


@dataclass
class ModuleInfo:
    name: str
    kind: str = "module"
    ports: list[Port] = field(default_factory=list)
    params: list[Param] = field(default_factory=list)
    signals: list[Port] = field(default_factory=list)
    interface_ports: dict[str, Port] = field(default_factory=dict)
    modports: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    instances: list[Instance] = field(default_factory=list)
    source_path: Path | None = None
    start: int = 0
    end: int = 0
    header_end: int = 0
    header_port_open: int | None = None
    header_port_close: int | None = None

    def declared_names(self) -> set[str]:
        return (
            {port.name for port in self.ports}
            | {signal.name for signal in self.signals}
            | {param.name for param in self.params}
        )
