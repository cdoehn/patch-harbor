"""Private one-shot worker: public API in, existing Apply JSON protocol out.

A separate process per poll preserves the watcher's current isolation and signal
behavior. The API remains a synchronous library: no CLI parser, implicit stdin,
console reporter or separate discovery logic is involved. This module is not an
additional public command or API surface.
"""
from __future__ import annotations

import json
import sys
from typing import TextIO

import patchharbor.api as api


def main(*, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Perform exactly one global automatic poll and return its completion code.

    Known failures already arrive as RunReport objects. Unexpected exceptions
    propagate to the process boundary rather than being reported as success or
    idle. Script output is only captured by Core in the mandatory Result log;
    it must never contaminate the worker's JSON transport.
    """
    result_stream = sys.stdout if stdout is None else stdout
    diagnostic_stream = sys.stderr if stderr is None else stderr
    report = api.apply_next()
    result_stream.write(json.dumps(
        report.apply_json_envelope(), ensure_ascii=True, allow_nan=False,
        separators=(",", ":"),
    ) + "\n")
    result_stream.flush()
    diagnostics = report.result_bundle.emergency_diagnostics_path
    if report.result_bundle.status is api.ResultBundleStatus.FAILED:
        if diagnostics is not None:
            # ASCII escaping keeps this optional diagnostic safe on all pipes.
            diagnostic_stream.write(
                "patchharbor: emergency diagnostics: "
                + json.dumps(str(diagnostics), ensure_ascii=True) + "\n"
            )
        else:
            diagnostic_stream.write(
                "patchharbor: Result publication failed; no emergency diagnostics path\n"
            )
        diagnostic_stream.flush()
    return report.process_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
