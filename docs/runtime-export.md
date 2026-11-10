# Export and use the installed Core runtime

Every official build emits wheel, sdist and the canonical Core-PYZ, independently
of tags. Normal wheel/pipx/venv and non-editable sdist installations contain the
resources needed to export their own runtime. Export needs Python >=3.10 and an
existing output directory, with no repository, Result, registration, Exchange,
Git executable, installer, network connection or build tools.

```bash
mkdir /absolute/path/runtime-output
patchharbor runtime export --output-dir /absolute/path/runtime-output --json
```

For 1.9.0 the output is `patchharbor-1.9.0.pyz`. A different installed version
exports its own version. The PYZ includes the public API and CLI, without the
watcher or third-party runtime dependencies. The normal installation retains
the watcher. The PYZ can export itself into another existing fresh directory:

```bash
python /absolute/path/patchharbor-1.9.0.pyz runtime export --output-dir /absolute/path/another-output --json
```

The public API from the installed environment is:

```python
from patchharbor import api
result = api.export_runtime('/absolute/path/runtime-output')
print(result.path, result.distribution_version, result.size, result.sha256)
```

`RuntimeExportResult` also includes `profile`, `requires_python`, `content_id`,
`source_commit` and `warnings`. An unavailable source commit is `None`; the
release manifest supplies independently checked release provenance. CLI JSON
uses `output_version: 1`, `command: "runtime.export"`, `success`, `result` and
`error` as described in [the API contract](python-api.md#runtime-export-since-180).
Paths are strings and warning tuples become arrays in JSON.

The output directory must already exist and be a normal directory, with no
symlink/reparse parent or parent traversal. Relative paths are resolved against
the caller's working directory. A preexisting output name, including a link,
is always protected. The exporter captures one validated runtime, writes a
private temporary file and uses native no-replace publication only after hash
and durability checks. Repeated exports to fresh directories are byte-identical
to this distribution's release PYZ and embedded Result runtime.

| Failure | CLI exit | API code |
| --- | --- | --- |
| Missing/invalid/unprepared own resources | 4 | `unavailable` |
| Invalid, missing or linked output directory | 4 | `unsafe_path` |
| Existing output name | 6 | `collision` |
| Write, verification or publication failure | 6 | `io` |
| Interruption | 130 | `interrupted` |

API failures are `api.RuntimeExportError`, with `code`, `reason`,
`unavailable_reason` and `published_path`. Standard argument/CLI errors retain
their normal conventions. CLI output failure uses exit 7. Failure before
publication leaves no incomplete final file and does not replace foreign data.
After publication a complete file can remain, including when reporting is
interrupted: inspect the destination and externally hash it before retrying.
`published_path` is supplied when publication is known; a process killed at an
atomic boundary may not report it. Cleanup warnings do not erase a successful
publication. A crash can leave an owned private temporary file.

An unprepared source/editable checkout may return
`unavailable/source_not_prepared`. Build with `scripts/build_release.py` and
install its wheel, or use its PYZ. Export never silently builds or downloads.

## Direct library use without a Result

Obtain the PYZ from the [release assets](release-runtime.md). Pin its full
expected SHA-256 from a trusted approval, independently of the downloaded
checksum file. Protect the runtime file and its parent from replacement for
the lifetime of the consuming process. In a fresh process, hash before import:

```python
from hashlib import sha256
from pathlib import Path
import sys

runtime = Path('/absolute/path/patchharbor-1.9.0.pyz')
expected = 'FULL_SHA256_FROM_TRUSTED_RELEASE_APPROVAL'
if sha256(runtime.read_bytes()).hexdigest() != expected:
    raise ValueError('runtime hash mismatch')
sys.path.insert(0, str(runtime))
from patchharbor import api
caps = api.integration_capabilities()
if caps.snapshot_contract_version != 1:
    raise RuntimeError('unsupported snapshot contract')
```

A version or a checksum downloaded beside the same file does not establish
trust by itself. Capability versions describe actual API contracts, not product
version numbers. The existing integration, snapshot and guarded-apply versions
remain 1. Safe-reference version 1 is available only on its supported Linux
x86-64 / CPython 3.10–3.14 host; check the actual capability before use.

The runnable [consumer proof](examples/verify_release_runtime.py) verifies the
external hash before loading public APIs. It creates only a fresh isolated
synthetic registered repository using the neighboring fixture helper, checks
the safe context and explicit plan boundaries, exports a safe Result, reads it
using its external hash, and verifies clean/dirty layers and unchanged source.
It is a demonstration of the consumer's policy decision, not authorization to
export an arbitrary real repository.

```bash
python -I -S -B docs/examples/verify_release_runtime.py --runtime /absolute/path/patchharbor-1.9.0.pyz --sha256 FULL_APPROVED_SHA256 --fixture-root /absolute/path/new-clean-fixture --case clean
python -I -S -B docs/examples/verify_release_runtime.py --runtime /absolute/path/patchharbor-1.9.0.pyz --sha256 FULL_APPROVED_SHA256 --fixture-root /absolute/path/new-dirty-fixture --case dirty
```

Keep both example files together. Each invocation prints a JSON proof containing
the runtime and Result hashes, capabilities, source inventory and snapshot
layers. SpecRoad adoption of these files and its own policy remains a separate
integration task.
