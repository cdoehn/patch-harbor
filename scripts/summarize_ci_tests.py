"""Add a diagnostic Actions summary without changing any acceptance decision."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.acceptance_catalog import BY_ARTIFACT
from tools.report_rendering import cell, table
from tools.test_results import validate
from tools.timing_model import case_timings, read_telemetry

MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250_000


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('missing, linked or oversized report')
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('non-finite JSON value: ' + value)
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError('report must be an object')
    return value


def count_cases(document):
    reports = document.get('reports')
    collections = document.get('collections')
    if not isinstance(reports, list) or len(reports) > MAX_ROWS or not isinstance(collections, dict):
        raise ValueError('invalid runtime report inventory')
    nodes = set()
    for collection in collections.values():
        if not isinstance(collection, list) or len(collection) > MAX_ROWS or any(not isinstance(n,str) for n in collection):
            raise ValueError('invalid collected test identities')
        nodes.update(collection)
        if len(nodes) > MAX_ROWS:
            raise ValueError('too many distinct test identities')
    grouped = {}
    for row in reports:
        if (not isinstance(row,dict) or row.get('nodeid') not in nodes
                or row.get('when') not in ('setup','call','teardown')
                or row.get('outcome') not in ('passed','failed','skipped')):
            raise ValueError('invalid test phase')
        grouped.setdefault(row['nodeid'], []).append(row)
    counts = dict.fromkeys(('passed','failed','skipped','xfail','xpass','not_run','incomplete'), 0)
    for nodeid in nodes:
        rows = grouped.get(nodeid, [])
        phases = {r['when']:r for r in rows if r.get('subtest') is None}
        duplicates = len(phases) != sum(r.get('subtest') is None for r in rows)
        if any(r['outcome']=='failed' for r in rows):
            state = 'failed'
        elif not rows or document.get('mode') == 'collection':
            state = 'not_run'
        elif duplicates or 'setup' not in phases or 'teardown' not in phases:
            state = 'incomplete'
        elif any(r.get('xfail') for r in rows):
            state = 'xfail' if any(r.get('xfail') and r['outcome']=='skipped' for r in rows) else 'xpass'
        elif phases['setup']['outcome']=='skipped' or phases.get('call',{}).get('outcome')=='skipped':
            state = 'skipped'
        elif set(phases)=={'setup','call','teardown'} and all(r['outcome']=='passed' for r in phases.values()):
            state = 'passed'
        else:
            state = 'incomplete'
        counts[state] += 1
    return counts


def summarize_document(document, build, commit):
    result = {'counts': count_cases(document), 'exitstatus': document.get('exitstatus'),
              'status': 'incomplete', 'binding': document.get('binding') if isinstance(document.get('binding'),dict) else {}, 'errors': [],
              'controller_observed_s': None, 'job_walltime_s': None, 'top': [],
              'timing_status': 'unavailable', 'preparation': [],
              'collection_outcomes': dict(Counter(str(r.get('outcome','unknown')) for r in document.get('collection_reports',[]) if isinstance(r,dict)))}
    try:
        validate(document)
        result['status'] = 'passed'
    except ValueError as exc:
        result['errors'].append(str(exc))
        if document.get('exitstatus') or result['counts']['failed']:
            result['status'] = 'failed'
    result['commit_binding_verified'] = bool(re.fullmatch(r'[0-9a-f]{40}', commit) and build and build.get('commit') == commit and build.get('binding') == document.get('binding'))
    if not result['commit_binding_verified']:
        result['errors'].append('report is not bound to the build evidence for this commit')
        if result['status'] == 'passed':
            result['status'] = 'unbound'
    try:
        data = read_telemetry(document)
        result['timing_status'] = data['status']
        controller = data['controller']
        if controller:
            result['controller_observed_s'] = controller['observed_elapsed_ns'] / 1_000_000_000
        cases = case_timings(document)
        result['top'] = sorted((c for c in cases if c['phases']['call']['duration_s'] is not None),
            key=lambda c:(-c['phases']['call']['duration_s'],c['nodeid']))[:10]
        result['preparation'] = [{'worker':worker, 'launch_to_registration_s':row.get('launch_to_registration_s'),
                                  'collection':row.get('collection')} for worker,row in data['workers'].items()]
    except (ValueError,KeyError,TypeError) as exc:
        result['errors'].append('timing: ' + str(exc))
    return result


def summarize(directory, artifact, environment):
    lane = BY_ARTIFACT.get(artifact)
    if lane is None:
        raise ValueError('unknown acceptance lane')
    commit = environment.get('GITHUB_SHA','')
    try:
        build = read_json(directory / 'patchharbor-build.json')
    except (OSError,ValueError):
        build = None
    suites = []
    for suite in lane.suites:
        path = directory / ('patchharbor-' + suite + '-tests.json')
        try:
            row = summarize_document(read_json(path),build,commit)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            row = {'status':'missing' if not path.exists() else 'invalid','errors':[str(exc)],'counts':None,'top':[]}
        suites.append(dict(row,suite=suite,report=path.name))
    return {'format_version':1, 'lane':lane.name, 'platform':lane.platform,'python':lane.python,
            'shell':lane.windows_engine or 'Bash', 'commit':commit,
            'run_id':environment.get('GITHUB_RUN_ID'), 'attempt':environment.get('GITHUB_RUN_ATTEMPT'),
            'artifact':artifact, 'artifact_url':environment.get('PH_SUMMARY_ARTIFACT_URL',''),
            'suites':suites,'aggregation':'per-suite executions; overlapping suites are not deduplicated',
            'job_walltime_s':None,'profiling_collected':False}


def render(document):
    lines = ['## PatchHarbor test results', '', cell(document['lane']),
             'Commit: ' + cell(document['commit']),
             'Run / attempt: ' + cell(document['run_id']) + ' / ' + cell(document['attempt']),
             'Lane platform / Python / shell: ' + ' / '.join(cell(document[k]) for k in ('platform','python','shell')),
             '', 'Counts are test executions per suite. Total job walltime is unmeasured.', '']
    url = document['artifact_url']
    parts = urlsplit(url)
    if parts.scheme=='https' and parts.hostname and not any(c in url for c in '()\r\n<> '):
        lines.extend(['[Full test artifacts](' + url + ')', ''])
    for suite in document['suites']:
        lines.extend(['### ' + cell(suite['suite']) + ' — ' + cell(suite['status']), ''])
        counts = suite['counts']
        if counts is not None:
            lines.extend([table(counts.keys(),[counts.values()]), '',
                'Observed platform / Python: ' + cell(suite['binding'].get('platform')) + ' / ' + cell(suite['binding'].get('python')),
                'Observed controller interval (seconds): ' + cell(suite['controller_observed_s']),
                'Timing completeness: ' + cell(suite['timing_status']),
                'Collection outcomes: ' + cell(json.dumps(suite['collection_outcomes'],sort_keys=True)),
                'Preparation: ' + cell(json.dumps(suite['preparation'],sort_keys=True),3000), '',
                table(('Test','Setup seconds','Call seconds','Teardown seconds'),
                    ((c['nodeid'],*(c['phases'][p]['duration_s'] for p in ('setup','call','teardown'))) for c in suite['top']))])
        lines.extend(['', 'Evidence: ' + cell(suite['report'])])
        lines.extend(cell(error) for error in suite['errors'])
        lines.append('')
    return '\n'.join(lines)[:128*1024] + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports-dir',type=Path,required=True)
    parser.add_argument('--artifact',default=os.environ.get('PH_SUMMARY_ARTIFACT'))
    parser.add_argument('--output',type=Path,default=os.environ.get('GITHUB_STEP_SUMMARY'))
    parser.add_argument('--best-effort',action='store_true',
                        help='Report diagnostic failures without changing existing test results')
    args = parser.parse_args(argv)
    if args.output is None:
        parser.error('an explicit output or GITHUB_STEP_SUMMARY is required')
    try:
        document = summarize(args.reports_dir,args.artifact,os.environ)
        with args.output.open('a',encoding='utf-8') as stream:
            stream.write(render(document))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('Additional test summary failed: ' + str(exc),file=sys.stderr)
        return 0 if args.best_effort else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
