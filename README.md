# OpenAI Planner

Lightweight planning generator that turns a project design file into an overview plan plus per-section implementation plans.

## Requirements
- Python 3.9+
- `openai` Python SDK
- `OPENAI_API_KEY` set in your environment

## Install
```bash
pip install openai
```

## Configure API key
```bash
export OPENAI_API_KEY="your-api-key"
```

## Usage
```bash
python3 plan_builder.py sample_design.md
```

## Output
- `docs/generated-plan/overview_plan.md`
- `docs/generated-plan/sections/*.md`

## Options
```bash
python3 plan_builder.py sample_design.md \
  --output-dir docs/generated-plan \
  --overview-model gpt-4o-mini \
  --detail-model gpt-4o-2024-08-06
```

## Notes
- The script uses the Responses API when available. If your SDK version is older, it falls back to Chat Completions automatically.

## Workflow
1. Put your project design into a single markdown file.
2. Run the generator to create an overview + detailed section plans.
3. Use the generated files as context for interactive development.
