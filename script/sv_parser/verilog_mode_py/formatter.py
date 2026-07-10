from __future__ import annotations

from .model import Param, Port


GROUP_TITLES = {
    "output": "Outputs",
    "inout": "Inouts",
    "input": "Inputs",
}


def direction_groups(ports: list[Port]) -> list[tuple[str, list[Port]]]:
    return [
        (direction, [port for port in ports if port.direction == direction])
        for direction in ("output", "inout", "input")
    ]


def declaration_prefix(port: Port) -> str:
    pieces = [port.direction]
    data_type = port.data_type.strip()
    if data_type and not (port.direction == "inout" and data_type == "wire"):
        pieces.append(data_type)
    if port.packed:
        pieces.append(port.packed)
    return " ".join(piece for piece in pieces if piece)


def format_declaration(indent: str, port: Port, comment: str = "") -> str:
    prefix = declaration_prefix(port)
    suffix = f" {comment}" if comment else ""
    return f"{indent}{prefix:<28}{port.name}{port.unpacked};{suffix}"


def format_parameter(indent: str, param: Param) -> str:
    prefix = "parameter"
    return f"{indent}{prefix:<28}{param.name};"


def port_actual(port: Port) -> str:
    if port.interface_type:
        return port.name
    if port.packed:
        return f"{port.name}{port.packed}"
    return port.name


def format_connection(indent: str, port: Port, actual: str, terminator: str) -> str:
    return f"{indent}.{port.name:<31}({actual}){terminator}"
