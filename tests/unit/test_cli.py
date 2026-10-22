from ai_detective.cli import build_parser


def test_help_parser_has_analyze_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["analyze", "incident.log", "--no-ai"])

    assert args.command == "analyze"
    assert args.log_file == "incident.log"
    assert args.no_ai is True

