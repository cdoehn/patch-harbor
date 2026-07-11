#!/usr/bin/env bash
set -Eeuo pipefail

PROGRAM="${0##*/}"

usage() {
  cat <<'EOF'
Usage:
  run_with_timeout.sh [options] -- COMMAND [ARG...]

Options:
  --timeout DURATION      Maximum runtime per attempt (default: 5m).
  --kill-after DURATION   Send SIGKILL this long after SIGTERM (default: 10s).
  --attempts NUMBER       Total attempts, including the first run (default: 2).
  --retry-delay DURATION  Delay before restarting a timed-out command (default: 1s).
  -h, --help              Show this help.

DURATION uses GNU timeout/sleep syntax, for example: 30s, 5m, 1h.

Only timeouts are retried. Ordinary command failures are returned immediately.
Exit status 124 means timeout; 137 can mean the forced SIGKILL fallback.
EOF
}

die() {
  printf '%s: %s\n' "$PROGRAM" "$*" >&2
  exit 2
}

timeout_duration="5m"
kill_after="10s"
attempts=2
retry_delay="1s"

while (($#)); do
  case "$1" in
    --timeout)
      (($# >= 2)) || die "--timeout requires a value"
      timeout_duration=$2
      shift 2
      ;;
    --kill-after)
      (($# >= 2)) || die "--kill-after requires a value"
      kill_after=$2
      shift 2
      ;;
    --attempts)
      (($# >= 2)) || die "--attempts requires a value"
      attempts=$2
      shift 2
      ;;
    --retry-delay)
      (($# >= 2)) || die "--retry-delay requires a value"
      retry_delay=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      die "missing '--' before the command"
      ;;
  esac
done

(($#)) || die "no command supplied"
[[ $attempts =~ ^[1-9][0-9]*$ ]] ||
  die "--attempts must be a positive integer"

command -v timeout >/dev/null 2>&1 || die "GNU timeout is required"
command -v sleep >/dev/null 2>&1 || die "sleep is required"

print_command() {
  printf ' %q' "$@"
}

for ((attempt = 1; attempt <= attempts; attempt++)); do
  printf '[%(%Y-%m-%dT%H:%M:%S%z)T] attempt %d/%d:' \
    -1 "$attempt" "$attempts" >&2
  print_command "$@" >&2
  printf '\n' >&2

  set +e
  timeout \
    --signal=TERM \
    --kill-after="$kill_after" \
    "$timeout_duration" \
    "$@"
  status=$?
  set -e

  if ((status == 0)); then
    exit 0
  fi

  if ((status != 124 && status != 137)); then
    printf '%s: command failed with status %d; not retrying\n' \
      "$PROGRAM" "$status" >&2
    exit "$status"
  fi

  if ((attempt == attempts)); then
    printf '%s: command timed out after %s on all %d attempt(s)\n' \
      "$PROGRAM" "$timeout_duration" "$attempts" >&2
    exit "$status"
  fi

  printf '%s: command timed out after %s; restarting after %s\n' \
    "$PROGRAM" "$timeout_duration" "$retry_delay" >&2
  sleep "$retry_delay"
done
