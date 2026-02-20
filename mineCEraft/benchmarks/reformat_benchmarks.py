"""Reformat benchmark JSON files per formatting.md.

Reformatting changes ONLY whitespace (newlines, indentation). All content is
preserved exactly: numbers stay as written (e.g. 62e6 or 62000000), strings
unchanged. No parse-then-serialize; we tokenize preserving raw literals then
pretty-print from the token stream.
"""
import re
from pathlib import Path


def tokenize(s):
    """Yield (kind, raw) where raw is exact substring. Preserves 62e6, "strings", etc."""
    i = 0
    n = len(s)
    while i < n:
        if s[i] in ' \t\n\r':
            i += 1
            continue
        if s[i] in '[{]},:':
            yield (s[i], s[i])
            i += 1
            continue
        if s[i] == '"':
            start = i
            i += 1
            while i < n:
                if s[i] == '\\':
                    i += 2
                    continue
                if s[i] == '"':
                    i += 1
                    break
                i += 1
            yield ('string', s[start:i])
            continue
        # number: -? digit+ (. digit+)? ([eE][+-]? digit+)?
        if s[i] == '-' or s[i].isdigit():
            start = i
            if s[i] == '-':
                i += 1
            while i < n and s[i].isdigit():
                i += 1
            if i < n and s[i] == '.':
                i += 1
                while i < n and s[i].isdigit():
                    i += 1
            if i < n and s[i] in 'eE':
                i += 1
                if i < n and s[i] in '+-':
                    i += 1
                while i < n and s[i].isdigit():
                    i += 1
            yield ('number', s[start:i])
            continue
        # literal true / false / null
        for lit in ('true', 'false', 'null'):
            if s[i:i + len(lit)] == lit and (i + len(lit) >= n or s[i + len(lit)] in ' \t\n\r,}]'):
                yield ('literal', s[i:i + len(lit)])
                i += len(lit)
                break
        else:
            i += 1  # skip unknown
    return


def parse_value(tokens):
    it = iter(tokens)
    tok = None

    def peek():
        nonlocal tok
        if tok is None:
            try:
                tok = next(it)
            except StopIteration:
                tok = ('', '')
        return tok

    def consume():
        nonlocal tok
        p = peek()
        tok = None
        return p

    def value():
        kind, raw = consume()
        if kind == '[':
            out = []
            while peek()[0] != ']':
                out.append(value())
                if peek()[0] == ',':
                    consume()
            consume()  # ]
            return ('array', out)
        if kind == '{':
            out = []
            while peek()[0] != '}':
                k = value()
                if k[0] != 'string':
                    raise ValueError('expected string key')
                consume()  # :
                v = value()
                out.append((k[1], v))
                if peek()[0] == ',':
                    consume()
            consume()  # }
            return ('object', out)
        if kind == 'string':
            return ('string', raw)
        if kind == 'number':
            return ('number', raw)
        if kind == 'literal':
            return ('literal', raw)
        raise ValueError('unexpected token ' + str(kind))

    return value()


def compact_emit(node):
    """Emit node as single line. Per formatting.md: space after ':' and ',' everywhere."""
    if node[0] in ('string', 'number', 'literal'):
        return node[1]
    if node[0] == 'array':
        return '[' + ', '.join(compact_emit(c) for c in node[1]) + ']'
    if node[0] == 'object':
        parts = [k + ': ' + compact_emit(v) for k, v in node[1]]
        return '{' + ', '.join(parts) + '}'
    return ''


def emit(node, indent_base=0, context='root'):
    """Emit formatted JSON following formatting.md. context: root | item | prompts | checks_outer."""
    if node[0] == 'array':
        if context == 'root':
            lines = ['[']
            for i, child in enumerate(node[1]):
                lines.append(emit(child, 2, 'item'))
                if i < len(node[1]) - 1:
                    lines[-1] += ','
                lines.append('')
            lines.append(']')
            return '\n'.join(lines)
        if context == 'item':
            return emit_object_item(node[1], indent_base)
        if context == 'prompts':
            parts = ['[']
            for i, child in enumerate(node[1]):
                parts.append('\n      ' + compact_emit(child) + (',' if i < len(node[1]) - 1 else ''))
            parts.append('\n    ]')
            return ''.join(parts)
        if context == 'checks_outer':
            parts = ['[']
            for ti, turn in enumerate(node[1]):
                part = '\n        ['
                for ci, check in enumerate(turn[1]):
                    part += '\n            ' + compact_emit(check) + (',' if ci < len(turn[1]) - 1 else '')
                part += '\n        ]' + (',' if ti < len(node[1]) - 1 else '')
                parts.append(part)
            parts.append('\n    ]')
            return ''.join(parts)
        # generic array (multi-turn etc.)
        parts = ['[']
        for i, child in enumerate(node[1]):
            parts.append('\n' + ' ' * (indent_base + 2) + emit(child, indent_base + 2, '') + (',' if i < len(node[1]) - 1 else ''))
        parts.append('\n' + ' ' * indent_base + ']')
        return ''.join(parts)
    if node[0] == 'object':
        if context == 'item':
            return emit_object_item(node[1], indent_base)
        return emit_object(node[1], indent_base, context)
    if node[0] in ('string', 'number', 'literal'):
        return node[1]
    return ''


def emit_object_item(pairs, indent_base):
    """Emit one top-level object: prompts array then checks array with formatting.md layout."""
    prompts_val = None
    checks_val = None
    for k, v in pairs:
        if k == '"prompts"':
            prompts_val = v
        elif k == '"checks"':
            checks_val = v
    out = [
        '  {',
        '    "prompts": ' + emit(prompts_val, 4, 'prompts') + ',',
        '    "checks": ' + emit(checks_val, 4, 'checks_outer'),
        '  }'
    ]
    return '\n'.join(out)


def emit_object(pairs, indent_base, context=''):
    parts = []
    for k, v in pairs:
        if parts:
            parts.append(' ')
        parts.append(k + ':')
        if v[0] in ('string', 'number', 'literal'):
            parts.append(v[1])
        else:
            parts.append(emit(v, indent_base + 2, context))
    return ''.join(parts)


def reformat_one(content):
    tokens = list(tokenize(content))
    root = parse_value(tokens)
    return emit(root)


def main():
    bench_dir = Path(__file__).resolve().parent
    for path in sorted(bench_dir.glob('*.json')):
        if path.name == 'builder.json':
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except Exception as e:
            print(path.name, 'read error:', e)
            continue
        try:
            out = reformat_one(content)
        except Exception as e:
            print(path.name, 'reformat error:', e)
            continue
        path.write_text(out, encoding='utf-8')
        print('Formatted:', path.name)


if __name__ == '__main__':
    main()
