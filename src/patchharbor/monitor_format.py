"""Small terminal-safe formatting helpers; original facts retain full values."""
from datetime import datetime, timezone
import re
import unicodedata

COLORS = {'clean': '32', 'dirty': '31', 'unknown': '90', 'title': '1;37',
          'warning': '33', 'running': '1;36', 'future': '35', 'selected': '1;37',
          'success': '32', 'failure': '31', 'waiting': '90'}
IDENTIFIER = re.compile(r'(?<![\w])(?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{64}|[0-9a-f]{40}|[0-9a-f]{32}|[0-9a-f]{16})(?![\w])', re.I)
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})')
SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


def safe_text(value):
    return ''.join(c if not unicodedata.category(c).startswith('C') else '?' for c in str(value))


def cell_width(char):
    return 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1


def crop(value, width):
    result, used = '', 0
    for char in safe_text(value):
        size = cell_width(char)
        if used + size > width:
            break
        result += char
        used += size
    return result


def fit(value, width):
    value = crop(value, width)
    return value + ' ' * max(0, width - sum(cell_width(c) for c in value))


def short_id(value, full=False):
    if value is None:
        return '—'
    value = str(value)
    return value if full or len(value) <= 6 else value[:6] + '...'


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def duration(seconds):
    if seconds is None or seconds < 0:
        return 'unbekannt'
    seconds = int(seconds)
    if seconds < 60:
        return f'{seconds}s'
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m {seconds:02}s'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {minutes:02}m'
    days, hours = divmod(hours, 24)
    return f'{days}d {hours}h'


def elapsed(value, now=None):
    parsed = timestamp(value)
    if parsed is None:
        return None
    return max(0, ((now or datetime.now(timezone.utc)) - parsed).total_seconds())


def age(value, now=None):
    seconds = elapsed(value, now)
    return 'Zeit unbekannt' if seconds is None else 'vor ' + duration(seconds)


def local_time(value, now=None):
    parsed = timestamp(value)
    if parsed is None:
        return '--:--:--'
    local = parsed.astimezone()
    today = (now or datetime.now(timezone.utc)).astimezone().date()
    return local.strftime('%H:%M:%S' if local.date() == today else '%d.%m. %H:%M')


def human_text(value, *, full=False, now=None):
    value = STAMP.sub(lambda m: local_time(m.group(), now), safe_text(value))
    return value if full else IDENTIFIER.sub(lambda m: short_id(m.group()), value)


def symbol(status, frame=0):
    return {'success': '✓', 'failure': '×', 'running': SPINNER[frame % len(SPINNER)]}.get(status, '·')


def wrap(value, width):
    """Wrap even long IDs/paths so full mode never silently clips a value."""
    value = safe_text(value)
    width = max(1, width)
    while value:
        part = crop(value, width)
        if not part:
            part = '?'
            value = value[1:]
        else:
            value = value[len(part):]
        yield part


def render_spans(spans, width, color):
    output, remaining = '', width
    for text, style in spans:
        text = crop(text, remaining)
        remaining -= sum(cell_width(c) for c in text)
        output += f'\x1b[{COLORS[style]}m{text}\x1b[0m' if color and style in COLORS else text
    return output
