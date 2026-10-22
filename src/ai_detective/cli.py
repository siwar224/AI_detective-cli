"""Interface en ligne de commande minimale du projet."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .analyzer.classifier import classify_event
from .analyzer.deterministic import analyze_events
from .config import DEFAULT_MAX_FILE_SIZE_BYTES, DEFAULT_MAX_LINES
from .parser.log_parser import parse_file
from .validation import InputFileError


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
    analyze_parser.add_argument(
        "--max-size-mb",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_BYTES // (1024 * 1024),
        help="Maximum input file size in MiB.",
    )
    analyze_parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help="Maximum number of input lines.",
    )
    return parser


def main() -> None:
    """Point d'entrée de la CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        path = Path(args.log_file)
        try:
            events = parse_file(
                path,
                max_size_bytes=args.max_size_mb * 1024 * 1024,
                max_lines=args.max_lines,
            )
        except (InputFileError, ValueError) as exc:
            parser.error(str(exc))
        analysis = analyze_events(events)
        categories = Counter(
            category
            for event in events
            if (category := classify_event(event)) is not None
        )

        print(f"Analyzed {len(events)} line(s) from {path}")
        print(f"Formats: {Counter(event.source_format for event in events)}")
        print(f"Parse status: {Counter(event.parse_status for event in events)}")
        print(f"Error categories: {dict(categories)}")
        print(f"Levels: {analysis.levels_count}")
        print("Top errors:")
        for error in analysis.top_errors:
            print(
                f"  {error.count}x {error.message} "
                f"(lines: {error.line_numbers})"
            )
        print(f"Timeline events: {len(analysis.timeline)}")
        print(f"Error peaks: {len(analysis.error_peaks)}")
        if analysis.limitations:
            print("Limitations:")
            for limitation in analysis.limitations:
                print(f"  - {limitation}")

        for event in events:
            category = classify_event(event) or "-"
            print(
                f"line {event.line_number}: {event.level or '-':<8} "
                f"{event.parse_status:<7} {category:<16} {event.message or event.raw_line}"
            )

