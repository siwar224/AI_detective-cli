"""Interface en ligne de commande minimale du projet."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Construit le parser CLI sans exécuter d'analyse."""
    parser = argparse.ArgumentParser(
        prog="ai-detective",
        description="Analyse des logs techniques avec des preuves vérifiables.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyser un fichier de logs (fonctionnalité à venir).",
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
        parser.error("L'analyse sera implémentée dans une prochaine étape.")

