from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SourceInspection:
    product: str
    version: str | None = None
    connection_ok: bool = False
    capabilities: dict[str, bool] = field(default_factory=dict)
    available_methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NormalizedIPAddress:
    address: str
    prefix_length: int | None = None
    vrf: str | None = None
    hostname: str | None = None
    dns_name: str | None = None
    description: str | None = None
    status: str | None = None
    owner_name: str | None = None
    interface_name: str | None = None
    mac_address: str | None = None
    source_record_id: str | None = None
    source: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedHistoricalEvent:
    timestamp: datetime
    ip_address: str
    event_type: str
    source_event_type: str | None = None
    hostname: str | None = None
    dns_name: str | None = None
    owner_type: str | None = None
    owner_name: str | None = None
    interface_name: str | None = None
    mac_address: str | None = None
    vrf_name: str | None = None
    vrf_rd: str | None = None
    username: str | None = None
    previous_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    source_record_id: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)