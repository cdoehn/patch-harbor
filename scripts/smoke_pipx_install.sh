#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
KEEP_TEMP=0
SKIP_UNINSTALL=0
REPO_ARG=""
PIPX_BIN="${PIPX_BIN:-pipx}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TMP_ROOT=""
PIPX_HOME_VALUE=""
PIPX_BIN_DIR_VALUE=""
PIPX_MAN_DIR_VALUE=""

usage() {
  cat <<'HELP'
Usage:
  scripts/smoke_pipx_install.sh [--repo PATH] [--dry-run] [--keep-temp] [--skip-uninstall] [--pipx PATH] [--python PATH]

Runs an isolated pipx install smoke for the local PatchHarbor checkout.

The smoke uses temporary PIPX_HOME, PIPX_BIN_DIR, and PIPX_MAN_DIR directories so it does not modify the user's normal pipx environment.

Checks performed:
  - validate pyproject metadata for the local checkout
  - pipx install --force --editable REPO
  - patchharbor --help
  - patchharbor --version
  - patchharbor doctor --repo REPO
  - patchharbor check-env --repo REPO --no-defaults
  - pipx uninstall patchharbor unless --skip-uninstall is set

Options:
  --repo PATH        repository checkout to install; defaults to the current Git root
  --dry-run          print the commands without executing pipx or patchharbor
  --keep-temp        keep the temporary pipx directories after a real run
  --skip-uninstall   leave the temporary pipx install in place until cleanup
  --pipx PATH        pipx executable; defaults to PIPX_BIN or pipx
  --python PATH      Python executable for PIPX_DEFAULT_PYTHON; defaults to PYTHON_BIN or python3
  -h, --help         show this help
HELP
}

log() {
  printf 'pipx-smoke: %s\n' "$*"
}

die() {
  printf 'pipx-smoke: error: %s\n' "$*" >&2
  exit 2
}

quote_cmd() {
  local item
  for item in "$@"; do
    printf '%q ' "$item"
  done
  printf '\n'
}

cleanup() {
  if [ "$KEEP_TEMP" -eq 0 ] && [ -n "${TMP_ROOT:-}" ] && [ -d "$TMP_ROOT" ]; then
    rm -rf "$TMP_ROOT"
  fi
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || die "--repo requires a path"
      REPO_ARG="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --keep-temp)
      KEEP_TEMP=1
      shift
      ;;
    --skip-uninstall)
      SKIP_UNINSTALL=1
      shift
      ;;
    --pipx)
      [ "$#" -ge 2 ] || die "--pipx requires a path"
      PIPX_BIN="$2"
      shift 2
      ;;
    --python)
      [ "$#" -ge 2 ] || die "--python requires a path"
      PYTHON_BIN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

resolve_repo_root() {
  local start="$1"
  local root=""
  if root="$(git -C "$start" rev-parse --show-toplevel 2>/dev/null)"; then
    printf '%s\n' "$root"
    return 0
  fi
  return 1
}

if [ -n "$REPO_ARG" ]; then
  [ -d "$REPO_ARG" ] || die "repository path does not exist: $REPO_ARG"
  REPO_ROOT="$(resolve_repo_root "$REPO_ARG")" || die "repository path is not inside a Git worktree: $REPO_ARG"
else
  REPO_ROOT="$(resolve_repo_root "$(pwd)")" || die "current directory is not inside a Git worktree"
fi

[ -f "$REPO_ROOT/pyproject.toml" ] || die "pyproject.toml missing in repository: $REPO_ROOT"
[ -d "$REPO_ROOT/src/patchharbor" ] || die "src/patchharbor package missing in repository: $REPO_ROOT"

"$PYTHON_BIN" - "$REPO_ROOT/pyproject.toml" <<'PYEOF'
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

path = Path(sys.argv[1])
data = tomllib.loads(path.read_text(encoding="utf-8"))
project = data.get("project", {})
scripts = project.get("scripts", {})
if project.get("name") != "patchharbor":
    raise SystemExit("project.name must be patchharbor")
if scripts.get("patchharbor") != "patchharbor.cli:main":
    raise SystemExit("project.scripts.patchharbor must be patchharbor.cli:main")
PYEOF

if [ "$DRY_RUN" -eq 0 ] && ! command -v "$PIPX_BIN" >/dev/null 2>&1; then
  die "pipx executable not found: $PIPX_BIN"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  TMP_ROOT="${TMPDIR:-/tmp}/patchharbor-pipx-smoke-dry-run"
else
  TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/patchharbor-pipx-smoke.XXXXXX")"
fi

PIPX_HOME_VALUE="$TMP_ROOT/pipx-home"
PIPX_BIN_DIR_VALUE="$TMP_ROOT/pipx-bin"
PIPX_MAN_DIR_VALUE="$TMP_ROOT/pipx-man"
PATCHHARBOR_BIN="$PIPX_BIN_DIR_VALUE/patchharbor"

mkdir -p "$PIPX_HOME_VALUE" "$PIPX_BIN_DIR_VALUE" "$PIPX_MAN_DIR_VALUE"

run_with_pipx_env() {
  printf 'PIPX_HOME=%q PIPX_BIN_DIR=%q PIPX_MAN_DIR=%q PIPX_DEFAULT_PYTHON=%q ' \
    "$PIPX_HOME_VALUE" "$PIPX_BIN_DIR_VALUE" "$PIPX_MAN_DIR_VALUE" "$PYTHON_BIN"
  quote_cmd "$@"
  if [ "$DRY_RUN" -eq 0 ]; then
    PIPX_HOME="$PIPX_HOME_VALUE" \
    PIPX_BIN_DIR="$PIPX_BIN_DIR_VALUE" \
    PIPX_MAN_DIR="$PIPX_MAN_DIR_VALUE" \
    PIPX_DEFAULT_PYTHON="$PYTHON_BIN" \
      "$@"
  fi
}

run_installed_patchharbor() {
  quote_cmd "$PATCHHARBOR_BIN" "$@"
  if [ "$DRY_RUN" -eq 0 ]; then
    [ -x "$PATCHHARBOR_BIN" ] || die "installed patchharbor executable missing: $PATCHHARBOR_BIN"
    "$PATCHHARBOR_BIN" "$@"
  fi
}

log "repo: $REPO_ROOT"
log "temporary pipx root: $TMP_ROOT"
if [ "$DRY_RUN" -eq 1 ]; then
  log "dry-run: commands will be printed but not executed"
fi

run_with_pipx_env "$PIPX_BIN" install --force --editable "$REPO_ROOT"

if [ "$DRY_RUN" -eq 1 ]; then
  run_installed_patchharbor --help
  run_installed_patchharbor --version
  run_installed_patchharbor doctor --repo "$REPO_ROOT"
  run_installed_patchharbor check-env --repo "$REPO_ROOT" --no-defaults
else
  run_installed_patchharbor --help >/dev/null
  run_installed_patchharbor --version >/dev/null
  run_installed_patchharbor doctor --repo "$REPO_ROOT" >/dev/null
  run_installed_patchharbor check-env --repo "$REPO_ROOT" --no-defaults >/dev/null
fi

if [ "$SKIP_UNINSTALL" -eq 0 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    run_with_pipx_env "$PIPX_BIN" uninstall patchharbor
  else
    run_with_pipx_env "$PIPX_BIN" uninstall patchharbor >/dev/null
  fi
else
  log "skip uninstall requested"
fi

log "ok"
