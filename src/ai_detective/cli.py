"""Interface en ligne de commande minimale du projet."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .analyzer.classifier import classify_event
from .parser.log_parser import parse_file


def build_parser() -> argparse.ArgumentParser:
    """Construit le parser CLI sans exécuter d'analyse."""
    parser = argparse.ArgumentParser(
        prog="ai-detective",
        description="Analyse des logs techniques avec des preuves vérifiables.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyser un fichier de logs.",
    )
    analyze_parser.add_argument("log_file", help="Chemin du fichier de logs.")
    analyze_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Limiter l'exécution à l'analyse déterministe.",
    )
    return parser


def main() -> None:
    """Point d'entrée de la CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        path = Path(args.log_file)
        if not path.is_file():
            parser.error(f"Log file not found: {path}")

        events = parse_file(path)
        categories = Counter(
            category
            for event in events
            if (category := classify_event(event)) is not None
        )

        print(f"Analyzed {len(events)} line(s) from {path}")
        print(f"Formats: {Counter(event.source_format for event in events)}")
        print(f"Parse status: {Counter(event.parse_status for event in events)}")
        print(f"Error categories: {dict(categories)}")

        for event in events:
            category = classify_event(event) or "-"
            print(
                f"line {event.line_number}: {event.level or '-':<8} "
                f"{event.parse_status:<7} {category:<16} {event.message or event.raw_line}"
            )

