"""Extract the executable bootstrap supplied by the actual handoff resource."""


def bootstrap_program(template: bytes) -> str:
    text = template.decode('utf-8').replace('\r\n', '\n')
    marker = '# PATCHHARBOR-PYZ-BOOTSTRAP\n'
    candidates = [part.split('\n```', 1)[0] for part in text.split('```python\n')[1:]
                  if part.startswith(marker)]
    if len(candidates) != 1:
        raise ValueError('handoff does not provide exactly one executable bootstrap')
    program = candidates[0].removeprefix(marker)
    compile(program, '<embedded PYZ bootstrap>', 'exec')
    return program
