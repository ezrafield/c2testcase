from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    id: str
    name: str
