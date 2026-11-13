"""Read the standalone helper supplied by the actual handoff resource."""


def bootstrap_program(source: bytes) -> str:
    text = source.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    compile(text, '<standalone PYZ bootstrap>', 'exec')
    return text
