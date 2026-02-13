# MineCEraft

Our work is located in the `mineCEraft` folder.

## Benchmark Categories

Benchmark files under `mineCEraft/benchmarks/` use the following prefixes:

| Prefix | Meaning |
|--------|---------|
| **bde** | Building Elements |
| **bld** | Building |
| **cse** | Civil/Structural Engineering |

## Quick Start

1. Follow Mindcraft's setup to configure the connection (Minecraft server + MindServer on port 8080).
2. Ensure `settings.js` uses `./builder.json` as the profile.
3. Run `mineCEraft/main.ipynb`.

## Workflow

`main.ipynb` loads prompts from `benchmarks/*.json`, sends them to the builder agent via `send_prompts.js`, extracts block placements from the generated action code using `action_processor.py`, and evaluates them with `eval_code/`.

## Key Files

| File | Purpose |
|------|---------|
| `main.ipynb` | End-to-end benchmark run and evaluation |
| `builder.json` | Builder agent profile (referenced by `settings.js`) |
| `category.json` | Evaluation categories: accuracy, safety, planning |
| `samples/` | Example JS action files for manual evaluation |

For documentation on `eval_code` functions, see the test notebooks (by category):

| Category | Test notebooks |
|----------|----------------|
| **accuracy** | [material](mineCEraft/eval_code/material_test.ipynb), [shape](mineCEraft/eval_code/shape_test.ipynb), [size](mineCEraft/eval_code/size_test.ipynb) |
| **safety** | [physical_plausibility](mineCEraft/eval_code/physical_plausibility_test.ipynb), [structural_stability](mineCEraft/eval_code/structural_stability_test.ipynb) |
| **planning** | [efficiency](mineCEraft/eval_code/efficiency_test.ipynb), [dependency](mineCEraft/eval_code/dependency_test.ipynb) |
| other | [integrated](mineCEraft/eval_code/_integrated_test.ipynb) |

---

## Acknowledgement

This project is built on [Mindcraft](https://github.com/mindcraft-bots/mindcraft). We thank the Mindcraft project for the underlying framework. For setup, installation, and detailed documentation, see [github.com/mindcraft-bots/mindcraft](https://github.com/mindcraft-bots/mindcraft).
