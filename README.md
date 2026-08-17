# AudioTran

## Requirements

- Python 3.11 or newer
- FFmpeg available on `PATH`

## Setup

Create and activate a virtual environment, then install the project in editable mode:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Test

Run the bootstrap smoke test with:

```powershell
python -m pytest tests/test_bootstrap.py -q
```
