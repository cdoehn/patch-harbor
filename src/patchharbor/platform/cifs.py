"""Read-only Linux CIFS cache hints for an owned Result publication retry budget."""
from pathlib import Path
import sys


def _mount_path(value: str) -> Path:
    for code, decoded in (("040", " "), ("011", "\t"), ("012", "\n"), ("134", "\\")):
        value = value.replace("\\" + code, decoded)
    return Path(value)


def cache_wait_budget(path: Path, mountinfo: str) -> int:
    """Five minutes minimum; allow two configured cache/close cycles plus margin.

    This is a retry policy, not a filesystem coherency or syscall deadline.
    Select the innermost mount, including a local mount nested below CIFS.
    """
    selected: tuple[int, str, str] | None = None
    for line in mountinfo.splitlines():
        try:
            left, right = line.split(" - ", 1)
            fields, tail = left.split(), right.split()
            mount = _mount_path(fields[4])
            if not path.is_relative_to(mount):
                continue
            row = (len(mount.parts), tail[0], fields[5] + "," + tail[2])
            if selected is None or row[0] >= selected[0]:
                selected = row
        except (ValueError, IndexError):
            continue
    if selected is None or selected[1] not in {"cifs", "smb3"}:
        return 300
    options = dict(option.split("=", 1) for option in selected[2].split(",") if "=" in option)
    try:
        attribute = int(options.get("acregmax", options.get("actimeo", "1")))
        close = int(options.get("closetimeo", "1"))
        if min(attribute, close) < 0:
            return 300
        return max(300, 2 * (attribute + close) + 10)
    except ValueError:
        return 300


def publication_wait_budget(path: Path) -> int:
    if sys.platform != "linux":
        return 300
    try:
        return cache_wait_budget(path.absolute(), Path("/proc/self/mountinfo").read_text())
    except (OSError, UnicodeError):
        return 300
