"""Read the deliberately restricted generated matrix values as JSON scalars."""
import json
import re


def workflow_matrices(text):
    groups = {}
    for group, body in re.findall(r'      # BEGIN acceptance-catalog: ([\w-]+)\n(.*?)      # END acceptance-catalog: \1\n', text, re.S):
        assert group not in groups
        rows = []
        for line in body.splitlines():
            match = re.fullmatch(r'          (- |  )([a-z_]+): (.+)', line)
            if match:
                if match[1] == '- ':
                    rows.append({})
                assert rows and match[2] not in rows[-1]
                rows[-1][match[2]] = json.loads(match[3])
        groups[group] = rows
    return groups
