from collections.abc import Callable

IMPORTERS: dict[str, type] = {}


def register_importer(source_type: str) -> Callable:
    def decorator(importer: type) -> type:
        IMPORTERS[source_type] = importer
        importer.source_type = source_type
        return importer
    return decorator


def importer_for(source_type: str):
    return IMPORTERS.get(source_type)


def support_matrix():
    return [{"source_type": key, "name": getattr(value, "display_name", key), "support_level": value.support_level.value,
             "capabilities": sorted(cap.value for cap in value.capabilities),
             "implemented": getattr(value, "implemented", True)} for key, value in IMPORTERS.items()]