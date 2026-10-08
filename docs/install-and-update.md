# Installation and safe updates

PatchHarbor requires Python 3.12 or newer. The normal wheel/sdist installation
provides both `patchharbor` and `patchharbor-watcher`; the Core-PYZ deliberately
does not include the watcher. Git and the declared Bash/PowerShell interpreter
are needed for repository execution, not for static pack/reference checks.

## Choose the artifact and interpreter

Use a wheel from a trusted build or a reviewed source checkout at the intended
commit. Compare its complete SHA-256 with the build's trusted artifact record.
A digest supplied only by an unknown sender is not authentication. The version
in the source tree is not evidence that an index release or Git tag exists.
The [acceptance plan](../planning/pyz-pack/commit-plan.md) records release gates;
`patchharbor --version` reports the executable you are actually invoking.

With an existing pipx and Python 3.12+ on POSIX:

```bash
python3 --version
pipx install --python python3 /absolute/path/patchharbor-1.3.0-py3-none-any.whl
patchharbor --version
patchharbor-watcher --help
```

Ensure pipx's application directory is on PATH. `pipx list` shows the environment
it manages; `command -v patchharbor` locates the selected POSIX executable.
Use an explicit interpreter path if `python3` is older than 3.12. On Windows,
use the same pipx commands with Windows paths and an available Python 3.12+
executable; `Get-Command patchharbor` shows which executable PowerShell selects.

For a reviewed local source checkout, `pipx install /absolute/path/to/checkout`
is also supported. The build backend prepares the runtime resources during
installation; build dependencies may need to be installed/downloaded then.
Point at the intended checked-out state, not an assumed branch or tag.
For an offline install, provide the wheel and an already usable installer.
Normal installation is distinct from the stdlib-only PYZ bootstrap.

## Dedicated venv instead of pipx

pipx is optional. For example on POSIX, after confirming `python3` is 3.12+:

```bash
python3 -m venv /absolute/path/to/patchharbor-env
/absolute/path/to/patchharbor-env/bin/python -m pip install /absolute/path/to/patchharbor.whl
/absolute/path/to/patchharbor-env/bin/patchharbor --version
```

Replace `patchharbor.whl` with the wheel's full valid filename. On Windows use
the venv's `Scripts/python.exe` and `Scripts/patchharbor.exe`. Invoke the explicit
paths or activate the environment; activation is not required. Avoid installing
into the operating system's Python environment. To import `patchharbor.api`, use
this environment's Python. A tool environment is not another application's
default import path.

For no-installation Core use, follow the [verified PYZ bootstrap](runtime-bootstrap.md).
Do not use `python -m patchharbor`: the installed module entrypoint is
`python -m patchharbor.cli`. The executable PYZ has its own `__main__`.

## Update while a watcher is installed

1. Let an active Apply finish and examine its Result/logs. Do not replace the
   installation under a running worker or interrupt it just to upgrade.
2. Stop the watcher. With the standard Linux user service:

   ```bash
   systemctl --user stop patchharbor-watcher.service
   systemctl --user status patchharbor-watcher.service
   ```

   The stopped service remains enabled if it was enabled before. For a foreground
   watcher, stop that process after its active Apply finishes.
3. Upgrade the **same installation that the service uses** with the reviewed
   new wheel. For pipx, a newer local wheel can replace the managed package:

   ```bash
   pipx install --force /absolute/path/patchharbor-1.3.0-py3-none-any.whl
   patchharbor --version
   ```

   In a dedicated venv, use its explicit Python with
   `-m pip install --upgrade /absolute/path/to/new-wheel.whl`. A rebuilt artifact
   with the same version needs the installer's explicit reinstall option; a
   version check alone cannot distinguish two builds with the same version.
4. Inspect `systemctl --user cat patchharbor-watcher.service`. The generated unit
   pins an absolute Python interpreter path. If that path changed, regenerate
   the unit from the new installation, then reload systemd:

   ```bash
   patchharbor-watcher --install-systemd-user-unit
   systemctl --user daemon-reload
   ```

   The generator replaces an existing regular unit; review any custom unit
   changes first. It does not enable or start the service. If the interpreter
   path and unit are unchanged, regeneration is unnecessary.
5. Restart the existing service and inspect its startup log:

   ```bash
   systemctl --user start patchharbor-watcher.service
   systemctl --user status patchharbor-watcher.service
   journalctl --user -u patchharbor-watcher.service -n 50
   ```

Do not start a second foreground watcher while the service runs. On Windows,
restart the foreground watcher using the upgraded installation. On Termux use
manual Apply; no Android background-service lifecycle is promised.

Upgrading changes the installed code, not the target repository registration.
Keep `.patchharbor/id`, the valid local configuration, central registry, locks
and replay records. Deleting those records is not an upgrade or repair method.
For pre-local-configuration installations, use the explicit
[manual configuration migration](repository-workflow.md#manual-upgrade-from-global-configuration).
Keep the version-matching `CHAT_INSTRUCTIONS.md`; new Results render their own
copy from the installed resources.

## Build artifacts for development

From the reviewed checkout, in a development environment with `.[dev]` installed:

```bash
python scripts/build_release.py --outdir dist
```

This builds wheel, sdist and the separate canonical Core-PYZ. It does not publish
a release, create a tag, install the artifacts, or replace a running watcher.
Run the [prescribed full parallel gates](test-parallelism.md) and retain the
artifact hashes/evidence for the actual source state before handing it off.
