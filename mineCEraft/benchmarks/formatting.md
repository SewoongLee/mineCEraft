# Benchmark JSON Formatting Guide

This document describes the formatting conventions for benchmark JSON files in this directory. Apply these rules when creating or editing benchmark files to keep them consistent and readable.

## Structure

Each benchmark file is a JSON array of objects. Each object has:
- `prompts`: array of prompt variants (each variant is a single-turn sequence)
- `checks`: array of check lists (one list per turn; typically one turn)

## Formatting Rules

### 1. Root Array
- Put the opening `[` on its own line.
- Each top-level object starts on a new line with 2-space indent.
- Separate items with a comma after the closing `}`.
- Put the closing `]` on its own line.

### 2. Prompts
- Keep each prompt variant on a single line: `["Build a bridge..."],`
- Do **not** expand the inner array across multiple lines.
- Format: `      ["prompt text"],`

### 3. Checks
- The outer `checks` array has one element per turn.
- The inner list (the actual list of check objects) uses 4-space indent.
- **Each check object (fn) on its own line.**
- Format each check as a compact object: `{"fn": "module.function_name", "args": {...}}`
- Use `separators=(',', ':')` for args (no spaces, compact).

Example:
```json
    "checks": [
        [
            {"fn": "physical_plausibility.is_ground_connected", "args": {}},
            {"fn": "shape.cluster_count_at_y_is", "args": {"y":0,"expected_count":2}},
            {"fn": "size.max_y_is_geq", "args": {"min_y":4}}
        ]
    ]
```

### 4. Indentation
- `prompts`: 4 spaces for the array, 6 spaces for each prompt line.
- `checks`: 4 spaces for outer array, 8 spaces for inner array, 12 spaces for each check line.

## Summary

| Element | Format |
|---------|--------|
| Root array | Newlines between items |
| Prompts | `["text"],` each on one line |
| Checks inner list | Each `{"fn": "...", "args": {...}}` on its own line |
| Args | Compact (no spaces, e.g. `{"y":0,"min_span":10}`) |

## Example Script (Python)

To reformat a benchmark file programmatically:

```python
import json
from pathlib import Path

def fmt_item(item):
    lines = ['  {', '    "prompts": [']
    for p in item['prompts']:
        s = json.dumps(p, ensure_ascii=False)
        lines.append('      ' + s + ',')
    if item['prompts']:
        lines[-1] = lines[-1].rstrip(',')
    lines.append('    ],')
    lines.append('    "checks": [')
    lines.append('        [')
    for c in item['checks'][0]:
        args = json.dumps(c['args'], ensure_ascii=False, separators=(',', ':'))
        lines.append('            {"fn": "' + c['fn'] + '", "args": ' + args + '},')
    if item['checks'][0]:
        lines[-1] = lines[-1].rstrip(',')
    lines.append('        ]')
    lines.append('    ]')
    lines.append('  }')
    return '\n'.join(lines)

path = Path('benchmarks/your_file.json')
with path.open(encoding='utf-8') as f:
    data = json.load(f)
out = ['[']
for i, item in enumerate(data):
    out.append(fmt_item(item))
    if i < len(data) - 1:
        out[-1] += ','
    out.append('')
out.append(']')
with path.open('w', encoding='utf-8') as f:
    f.write('\n'.join(out))
```
