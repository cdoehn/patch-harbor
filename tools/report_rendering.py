"""Small bounded standard-library rendering shared by local and Actions reports."""
import html
import json


def cell(value, limit=300):
    value = 'unknown' if value is None else str(value)
    value = ''.join(character if character.isprintable() else ' ' for character in value)
    return html.escape(value[:limit], quote=False).replace('|', '&#124;').replace('`', '&#96;')


def table(columns, rows, *, limit=100):
    lines = ['| ' + ' | '.join(cell(c) for c in columns) + ' |',
             '| ' + ' | '.join('---' for _ in columns) + ' |']
    for index, row in enumerate(rows):
        if index >= limit:
            lines.append('Additional rows omitted from this view.')
            break
        lines.append('| ' + ' | '.join(cell(v) for v in row) + ' |')
    return '\n'.join(lines)


def render_profile(document, format_name):
    if format_name == 'json':
        return json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False)
    lines = ['Local test measurements', cell(document.get('run_id', 'comparison')),
             'Status: ' + cell(document.get('status', 'complete'))]
    if 'ranking' in document:
        lines.extend(['', 'Unprofiled baseline, selected phase', table(
            ('Test','Phase','Median seconds','Min','Max','Samples'),
            ((r['nodeid'],r['phase'],r['median_s'],r['min_s'],r['max_s'],r['samples']) for r in document['ranking']))])
        lines.extend(['', 'Measurement completeness', table(('Mode','Warmup','Status','Test exit','Elapsed seconds'),
            ((r['mode'],r['warmup'],r['status'],r['test_exit_code'],r['elapsed_s']) for r in document['measurements']))])
        lines.extend(['', 'Investigation candidates; instrumented modes are separate', table(
            ('Rule','Test','Phase','Evidence','Limit'),
            ((r['rule'],r['nodeid'],r['phase'],json.dumps(r['evidence'],sort_keys=True),r['limitation']) for r in document['findings']))])
        lines.extend(['', 'Coverage: ' + cell(json.dumps(document['coverage'], sort_keys=True), 2000)])
    else:
        lines.extend(['', table(('Test','Phase','Before median','After median','Difference','Ratio'),
            ((r['nodeid'],r['phase'],r['before']['median_s'],r['after']['median_s'],r['difference_s'],r['ratio']) for r in document['comparisons'])),
            '', cell(document['limitation'], 2000)])
    rendered = '\n'.join(lines)
    if format_name == 'text':
        rendered = html.unescape(rendered)
    return rendered[:65536]
