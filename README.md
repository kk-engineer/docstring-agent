# docstring-agent

**Smart Python docstrings on autopilot.** Generate, audit, and repair docstrings using a NOLLM-first pipeline — template matching for trivial methods, heuristic generation for most functions, and selective LLM synthesis only where it matters.

```bash
docstring-agent generate          # add missing docstrings
docstring-agent audit             # score coverage & quality
docstring-agent repair            # fix low-quality docstrings
```

## Features

- **Three-tier generation** — Templates for boilerplate, heuristics for routine methods, LLM for complex code. Saves tokens without sacrificing quality.
- **Multi-style support** — Google, NumPy, and Sphinx docstring styles.
- **Quality scoring** — Multi-dimensional scoring (summary, args, returns, specificity, raises) with configurable thresholds.
- **Read-only audit** — Measure docstring coverage and quality across your codebase without touching files.
- **Targeted repair** — Heuristic section patching or surgical LLM repairs for flagged methods. Backup originals automatically.
- **Cyclomatic routing** — Routes methods to the right generator based on complexity, parameter count, and return type.
- **Smart caching** — Skips already-processed files across runs.

## Installation

```bash
pip install docstring-agent
```

Or with `uv`:

```bash
uv add docstring-agent
```

Requires Python 3.11+.

## Quick start

```bash
# Generate missing docstrings in the current directory
docstring-agent generate

# Preview changes without writing
docstring-agent generate --dry-run --show-summary

# Use NumPy-style docstrings
docstring-agent generate --style numpy

# Audit docstring quality
docstring-agent audit /path/to/project

# Export audit report as JSON
docstring-agent audit --format json --output report.json

# Repair flagged methods from an audit report
docstring-agent repair --report report.json --dry-run
```

## Commands

### `generate`

Add and improve docstrings across your Python project.

```
docstring-agent generate [REPO_PATH] [options]

Options:
  -c, --config FILE     Path to TOML config file
  --dry-run             Preview changes without writing
  --style STYLE         Docstring style: google, numpy, sphinx
  --improve / --no-improve  Improve existing docstrings
  --llm-only            Skip template/heuristic, send everything to LLM
  --no-llm              Skip LLM entirely (template + heuristic only)
  --show-summary        Print summary table after run
```

### `audit`

Read-only docstring coverage and quality analysis.

```
docstring-agent audit [REPO_PATH] [options]

Options:
  --format FORMAT       Output format: console, json, markdown (repeatable)
  --output FILE         Write report to file
  --threshold FLOAT     Quality score threshold 0.0–1.0 (default: 0.65)
  --min-coverage FLOAT  Coverage threshold 0.0–1.0 (default: 1.0)
  --include-private     Include private methods
  --include-dunders     Include dunder methods
  --sort-by FIELD       Sort flagged methods: score, name, file, complexity
  --fail-under FLOAT    Exit code 1 if mean quality below threshold
```

### `repair`

Fix docstrings flagged by an audit.

```
docstring-agent repair [REPO_PATH] [options]

Options:
  --report FILE         Load audit report JSON instead of running inline audit
  --dry-run             Preview repairs without writing
  --no-llm              Heuristic patching only
  --token-budget INT    Override LLM token budget (default: 50000)
  --no-backup           Skip .bak backup files
  --show-summary        Print repair summary table after run
```

## Configuration

Configuration is via `config.toml`. A default is created on first run. Key sections:

```toml
[llm]
provider = "nvidia"
model = "meta/llama-3.1-8b-instruct"

[docstring_gen]
docstring_style = "google"
complexity_threshold = 4
improve_existing = true

[audit]
quality_threshold = 0.65
min_coverage = 1.0

[repair]
token_budget = 50000
backup_originals = true
```

## Architecture

```
Source files  ──►  FileWalker  ──►  CSTParser  ──►  Enricher
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    ▼                  ▼                  ▼
                              TemplateGen        HeuristicGen         LLMGen
                              (trivial/dup)    (routine methods)   (complex code)
                                    │                  │                  │
                                    └──────────────────┼──────────────────┘
                                                       ▼
                                                  DocstringWriter
                                                       │
                                                  Repaired files

Audit pipeline (read-only):
  ──►  CoverageAuditor  ──►  QualityScorer  ──►  ReportFormatter

Repair pipeline:
  ──►  AuditReportReader  ──►  RepairPlanner  ──►  RepairExecutor  ──►  RepairVerifier
```

## How it works

1. **Discovery** — Walks the repository, collecting `.py` files while skipping vendored/ build directories.
2. **Parsing** — Uses `libcst` to extract every function, method, and class with its signature, body, existing docstring, and cyclomatic complexity.
3. **Routing** — Each method is routed to the appropriate generator based on complexity and heuristics:
   - **Template** — Trivial methods (`__init__`, `get_`/`set_` prefixes) and known dunders get simple templates.
   - **Heuristic** — Most methods get meaningful docstrings assembled from parameter info, return types, and body analysis.
   - **LLM** — Complex methods (high cyclomatic complexity, many parameters, or non-trivial return types) are batched and sent to the configured LLM.
4. **Writing** — Modified ASTs are written back atomically, with cache tracking to avoid redundant work.
5. **Audit** — Scans documented methods across 5 dimensions (summary, args, returns, specificity, raises) and flags anything below threshold.
6. **Repair** — Flags from an audit are routed to heuristic patchers for structural issues or surgical LLM calls for content problems, with guardrails to preserve what's already good.

## Development

```bash
uv sync                              # install dev dependencies
.venv/bin/python -m pytest tests/    # run tests
.venv/bin/python -m mypy src/        # type checking
.venv/bin/python -m ruff check src/  # linting
```

## License

MIT
