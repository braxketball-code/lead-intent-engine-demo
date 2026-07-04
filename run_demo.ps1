# Run the lead scoring demo (no API keys required)
Set-Location $PSScriptRoot
python -m src.pipeline --input data/sample_leads.json --output output --mode rules
