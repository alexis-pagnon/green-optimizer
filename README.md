# Nuit de l'Informatique 2025 – Green Optimizer - README

Groupe NoSleep4Us

## Prerequisites
- Python 3.10+ installed
- Recommended: virtual environment

## Setup
```bash
# Clone and enter the project
git clone <your-repo-url>
cd green-optimizer

# Create and activate a virtual environment (optional)
python -m venv .venv
```

Windows
```bash
.venv\Scripts\activate
```

macOS/Linux
```bash
source .venv/bin/activate
```

```bash
# Install dependencies
pip install -r requirements.txt

# Install playwright browsers:
python -m playwright install
```

## Launch the analysis dashboard
Interactive dashboard for exploring results.
```bash
python dashboard.py
```
- Opens a local server (printout will show the URL, e.g., http://127.0.0.1:5000).
- Ensure any required data files or configs are present (see project docs/config).

## Run the optimizer (CLI)
Command-line interface to run optimization.
```bash
python cli.py --url <url> --output <file_name>.file optimize 
```

## Project structure
- dashboard.py: analysis dashboard
- cli.py: optimization tool with command-line options
- requirements.txt: Python dependencies

## Troubleshooting
- Ensure all dependencies are installed.
- Use admin rights if facing permission issues.
