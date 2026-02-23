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
- Put a space after `:` and after `,` everywhere (same rule for check object and for args).

Example:
```json
    "checks": [
        [
            {"fn": "physical_plausibility.is_ground_connected", "args": {}},
            {"fn": "shape.cluster_count_at_y_is", "args": {"y": 0, "expected_count": 2}},
            {"fn": "size.max_y_is_geq", "args": {"min_y": 4}}
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
| Objects | Space after `:` and `,` (e.g. `{"fn": "...", "args": {"y": 0}}`) |

## Reformatting All Benchmarks

A script in this directory reformats every `*.json` file (except `builder.json`) to match the rules above. **Reformatting changes only whitespace** (newlines, indentation). All content is preserved exactly: numbers keep their form (e.g. `62e6` stays `62e6`, `62000000` stays `62000000`), strings and keys are unchanged.

```bash
cd mineCEraft/benchmarks
python reformat_benchmarks.py
```

Use **reformat_benchmarks.py** for formatting. Update it if there are bugs. It handles single- and multi-turn benchmarks and preserves all content (no re-serialization of numbers or strings).
