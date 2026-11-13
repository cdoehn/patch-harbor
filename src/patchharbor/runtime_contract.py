"""Immutable advertised capabilities; validators retain independent boundaries.

The standalone bootstrap receives these literals through the build renderer.
Reading this source for generation must never import the product runtime.
"""

OPERATIONS = ('inspect_task', 'validate_task', 'pack_task')
TASK_FORMATS = (3,)
RESULT_FORMATS = (5,)


def capabilities_document() -> dict:
    """Return new containers, so consumers cannot mutate shared policy."""
    return dict(operations=list(OPERATIONS), task_formats=list(TASK_FORMATS),
                result_formats=list(RESULT_FORMATS))
