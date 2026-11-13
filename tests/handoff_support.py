"""Small passive current-format fixtures; never execute their helper."""
from hashlib import sha256
import json
from patchharbor.bundle_handoff import BundleHandoff

def handoff(document, instructions=b"# Passive reference\n"):
    helper = b'raise AssertionError("passive helper executed")\n'
    document = dict(document, format_version=3,
        bootstrap=dict(path="tools/pyz_bootstrap.py", size=len(helper), sha256=sha256(helper).hexdigest()))
    return BundleHandoff(instructions, json.dumps(document).encode(), helper)
