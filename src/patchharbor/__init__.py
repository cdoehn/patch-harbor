"""PatchHarbor package."""

__version__ = "1.5.0"

# Bind the executing PYZ producer at package import. Source/editable use has
# no prepared identity. Do not read recipes or materialize archives here.
try:
    from patchharbor._pyz_identity import RESOURCE_ID as _pyz_resource_id
except ModuleNotFoundError as exc:
    if exc.name != __name__ + "._pyz_identity":
        raise
    _pyz_resource_id = None

__all__ = ["__version__"]
