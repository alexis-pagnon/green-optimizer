import argparse
import json
from analysis import run_analysis
from optimize import run_optimization

def main():
    parser = argparse.ArgumentParser(description="Green Optimizer - Module Analyse")
    parser.add_argument("command", choices=["analyze","optimize"], help="Commande à exécuter")
    parser.add_argument("--url", required=True, help="URL à analyser")
    parser.add_argument("--output", default="report.json", help="Fichier JSON de sortie")
    args = parser.parse_args()

    if args.command == "analyze":
        report = run_analysis(args.url)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"✔ Rapport généré : {args.output}")
    elif args.command == "optimize":
        report = run_optimization(args.url)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"✔ Rapport généré : {args.output}")

if __name__ == "__main__":
    main()
