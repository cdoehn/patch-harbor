"""Private native-event selection; platform libraries load only on creation."""
from pathlib import Path
import sys

from patchharbor_watcher.events import EventBackendError, EventErrorKind, EventSource


def open_event_source(directories: tuple[Path, ...]) -> EventSource:
    """Select native support lazily; unsupported systems fail before any polling."""
    if sys.platform == "win32":
        from patchharbor_watcher.platform.windows import WindowsEventSource
        return WindowsEventSource(directories)
    if sys.platform.startswith("linux"):
        from patchharbor_watcher.platform.linux import LinuxEventSource
        return LinuxEventSource(directories)
    raise EventBackendError(EventErrorKind.UNSUPPORTED, "native filesystem events are unavailable")
