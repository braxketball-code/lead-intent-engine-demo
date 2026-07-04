# Lead Intent Engine — Demo

Portfolio demo for **n8n + Python + AI lead scoring** workflows.

**Live repo:** https://github.com/braxketball-code/lead-intent-engine-demo

## Quick start

```powershell
python -m src.pipeline
```

No API keys required (rule-based scorer). Outputs JSON/CSV to `output/`.

## What it demonstrates

- Multi-source lead ingest
- 0–100 scoring with reasoning + tags
- Hot/warm/cool/cold tier routing
- n8n workflow template in `n8n/workflow-template.json`
- Optional LLM mode (`--mode openai` or `--mode xai`)

## Use in proposals

> Working demo: https://github.com/braxketball-code/lead-intent-engine-demo — same architecture I'd build for your V1.
