# MineCEraft

**MineCEraft** (Minecraft **C**onstruction **E**ngineering Benchmark) is an open-source benchmark for evaluating LLMs as construction engineers in Minecraft. It provides a safe, controllable environment to assess how well language models perform realistic construction engineering tasks with programmable and systematic evaluation.

Our work is located in the `mineCEraft` folder.

## Benchmark Categories

Benchmark files under `mineCEraft/benchmarks/` use the following prefixes:

| Prefix  | Meaning |
|---------|---------|
| `1-bde` | Building Elements |
| `2-bld` | Building |
| `3-cse` | Civil/Structural Engineering |

Subcategories:

- **Building Elements**: Foundations, Walls, Roofs and Columns, Frames
- **Buildings**: Basic Buildings, Multiple Rooms, Multiple Bedrooms, Multi-story Building, Accessibility & Human Factors, Unusual/Creative Requests, Resource Optimization, Single-turn Planning, Multi-turn Planning & Revision
- **Civil/Structural Engineering**: Basic Bridges, Arched Bridges, Vault, Dome

## Quick Start

1. Follow [Mindcraft's setup](https://github.com/mindcraft-bots/mindcraft) to configure the connection (Minecraft game + MindCraft server on port 15916).
2. Ensure `./builder.json` has your desired LLM set under the `model` key.
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

We provide test notebooks for each evaluation module. They serve as documentation, clarify how each criterion is assessed, and support maintainability. See the notebooks below (by category):

| Category | Test notebooks |
|----------|----------------|
| **accuracy** | [material](mineCEraft/eval_code/material_test.ipynb), [shape](mineCEraft/eval_code/shape_test.ipynb), [size](mineCEraft/eval_code/size_test.ipynb) |
| **safety** | [physical_plausibility](mineCEraft/eval_code/physical_plausibility_test.ipynb), [structural_stability](mineCEraft/eval_code/structural_stability_test.ipynb) |
| **planning** | [efficiency](mineCEraft/eval_code/efficiency_test.ipynb), [dependency](mineCEraft/eval_code/dependency_test.ipynb) |
| other | [integrated](mineCEraft/eval_code/_integrated_test.ipynb) |

---

## Acknowledgement

This project is built on [Mindcraft](https://github.com/mindcraft-bots/mindcraft). We thank the Mindcraft project for the underlying framework. For setup, installation, and detailed documentation, see [github.com/mindcraft-bots/mindcraft](https://github.com/mindcraft-bots/mindcraft).
