"""PatchHarbor package."""

__version__ = "1.2.1"

# A wheel-only literal captures the installed producer when this process first
# imports the package. Source/editable use has no prepared producer identity.
# Do not read recipes, import the provider or materialize archives at API import.
try:
    from patchharbor._runtime_identity import RESOURCE_ID as _runtime_resource_id
except ModuleNotFoundError as exc:
    if exc.name != __name__ + "._runtime_identity":
        raise
    _runtime_resource_id = None

__all__ = ["__version__"]
