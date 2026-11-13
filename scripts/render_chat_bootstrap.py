"""Check standalone chat resources and maintain literal runtime capabilities.

Builds call check(); --write only refreshes capability literals in the canonical
helper. No helper code is imported or executed and Markdown never embeds it.
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
import sys

BOOTSTRAP_NAME = "tools/pyz_bootstrap.py"
CAP_BEGIN = b"# BEGIN GENERATED RUNTIME CAPABILITIES\n"
CAP_END = b"# END GENERATED RUNTIME CAPABILITIES"


def render_capabilities(source: bytes, contract: bytes) -> bytes:
    """Copy reviewed literals without executing a bootstrap or product import."""
    tree = ast.parse(contract, feature_version=(3, 10))
    names = ('OPERATIONS', 'TASK_FORMATS', 'RESULT_FORMATS')
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    if target.id in values:
                        raise ValueError('ambiguous capability literal')
                    values[target.id] = ast.literal_eval(node.value)
    if set(values) != set(names):
        raise ValueError('missing capability literal')
    for name, value in values.items():
        expected_type = str if name == 'OPERATIONS' else int
        if (type(value) is not tuple or not value
                or any(type(v) is not expected_type for v in value)
                or len(set(value)) != len(value)
                or any(not v if expected_type is str else v < 1 for v in value)):
            raise ValueError('invalid capability literal')
    source = source.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    if source.count(CAP_BEGIN) != 1 or source.count(CAP_END) != 1:
        raise ValueError('expected exactly one capability region')
    before, _, rest = source.partition(CAP_BEGIN)
    _, separator, after = rest.partition(CAP_END)
    if not separator:
        raise ValueError('capability markers out of order')
    literals = ''.join(f'{name} = {values[name]!r}\n' for name in names).encode()
    generated = before + CAP_BEGIN + literals + CAP_END + after
    ast.parse(generated, feature_version=(3, 10))
    return generated



def _contents(root: Path) -> tuple[tuple[Path, bytes, bytes], ...]:
    script = root / BOOTSTRAP_NAME
    source = script.read_bytes()
    if not source or len(source) > 128 * 1024 or source.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid standalone bootstrap")
    source.decode("utf-8")
    program = render_capabilities(source, (root / 'src/patchharbor/runtime_contract.py').read_bytes())
    version_tree = ast.parse((root / 'src/patchharbor/__init__.py').read_bytes())
    versions = [ast.literal_eval(n.value) for n in version_tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets)]
    if len(versions) != 1 or type(versions[0]) is not str:
        raise ValueError('ambiguous producer version')
    program, count = re.subn(rb"(?m)^PATCHHARBOR_VERSION = [^\n]+$",
                            ('PATCHHARBOR_VERSION = ' + repr(versions[0])).encode(), program)
    if count != 1:
        raise ValueError('missing standalone helper version')
    template = (root / "CHAT_INSTRUCTIONS.md").read_bytes()
    if not template or len(template) > 128 * 1024 or template.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid chat template")
    text = template.decode("utf-8")
    if BOOTSTRAP_NAME not in text or '# PATCHHARBOR-PYZ-BOOTSTRAP' in text:
        raise ValueError("template must reference its separate helper without embedding code")
    return ((script, source, program),)


def check(root: Path) -> None:
    """Read-only capability and resource check before any build artifact."""
    if any(generated != original.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
           for _, original, generated in _contents(root)):
        raise ValueError("stale bootstrap: run python scripts/render_chat_bootstrap.py --write")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--write", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if args.check:
        check(args.root)
    else:
        # Validate the helper and its documentation before any write.
        for target, original, generated in _contents(args.root):
            if generated != original:
                target.write_bytes(generated)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, SyntaxError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
