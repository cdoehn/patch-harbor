"""Evaluate stable proof variants after complete report validation."""
from __future__ import annotations

from tools.acceptance_catalog import Lane, PROOFS, legacy_proofs, required_proofs
from tools.test_results import EvidenceError, validate


def evaluate_proofs(documents: dict[str, dict], lane: Lane) -> list[dict]:
    evidence = {}
    for report_name, document in documents.items():
        signature = validate(document)
        outcomes = {node: outcome for node, outcome, _ in signature[2]}
        assignments = (legacy_proofs(signature[0]) if document['format_version'] == 1
                       else document['proofs'])
        for node, proof in assignments.items():
            identity, variant = proof['id'], proof['variant']
            if identity not in PROOFS or variant not in PROOFS[identity]['variants']:
                raise EvidenceError('Unknown acceptance proof variant')
            key = identity, variant
            if key in evidence:
                raise EvidenceError('Duplicate acceptance proof across suite reports')
            evidence[key] = {'id': identity, 'variant': variant, 'nodeid': node,
                             'report': report_name, 'outcome': outcomes[node],
                             'test_format': document['format_version']}
    required = required_proofs(lane)
    missing = sorted(key for key in required if key not in evidence or evidence[key]['outcome'] != 'passed')
    if missing:
        raise EvidenceError('Missing or unpassed acceptance proof variants: ' + repr(missing))
    return [evidence[key] for key in sorted(required)]
