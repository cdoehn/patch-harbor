"""Exact product-version boundary shared by all native package consumers."""
from patchharbor import __version__

def require_bundle_version(value: object) -> None:
    if type(value) is str and value == __version__:
        return
    label = repr(value[:64]) if type(value) is str else "missing or invalid"
    raise ValueError(f"unsupported PatchHarbor package version {label}; "
                     f"running {__version__}; migration is not supported")
