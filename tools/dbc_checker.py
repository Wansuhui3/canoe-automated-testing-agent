"""
DBC Checker - Command-line tool for DBC file validation.

Usage:
    python tools/dbc_checker.py --input <dbc_file> [--fix] [--output <report_path>]
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dbc.parser import DBCParser
from src.dbc.validator import DBCValidator
from src.dbc.models import ValidationSeverity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DBC File Checker - Validate and fix DBC definitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/dbc_checker.py --input my_database.dbc
  python tools/dbc_checker.py --input my_database.dbc --fix
  python tools/dbc_checker.py --input my_database.dbc --output report.json
        """,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the DBC file to validate",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix fixable issues",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path for validation report (JSON)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )

    args = parser.parse_args()

    # Parse DBC file
    print(f"📋 Parsing DBC file: {args.input}")
    dbc_parser = DBCParser()
    try:
        model = dbc_parser.parse(args.input)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print(f"  ✅ Parsed: {len(model.messages)} messages, {len(model.nodes)} nodes")
    total_signals = sum(len(m.signals) for m in model.messages)
    print(f"  ✅ Total signals: {total_signals}")

    if args.verbose:
        for msg in model.messages:
            mux_info = ""
            if msg.get_multiplexer_signal():
                mux_info = " [MUX]"
            print(f"    📨 {msg.name} (0x{msg.id:X}, DLC={msg.length}){mux_info}")
            for sig in msg.signals:
                type_tag = {
                    "normal": "",
                    "multiplexer": " [MUX]",
                    "multiplexed": f" [mux={sig.mux_value}]",
                }.get(sig.signal_type.value, "")
                print(f"      └── {sig.name}: bit {sig.start_bit}:{sig.bit_length} "
                      f"({sig.byte_order.value}){type_tag}")

    # Validate
    print(f"\n🔍 Validating DBC definitions...")
    validator = DBCValidator(auto_fix=args.fix)
    result = validator.validate(model)

    # Report results
    if result.error_count == 0 and result.warning_count == 0:
        print("  ✅ No issues found! DBC file is clean.")
    else:
        if result.error_count > 0:
            print(f"  ❌ Errors: {result.error_count}")
        if result.warning_count > 0:
            print(f"  ⚠️  Warnings: {result.warning_count}")

        for issue in result.issues:
            icon = {
                ValidationSeverity.ERROR: "❌",
                ValidationSeverity.WARNING: "⚠️",
                ValidationSeverity.INFO: "ℹ️",
            }.get(issue.severity, "  ")
            print(f"  {icon} {issue}")

    if result.auto_fixed:
        print(f"\n🔧 Auto-fixed: {len(result.auto_fixed)} issues")

    # Save report
    if args.output:
        import json
        report_data = {
            "filename": result.filename,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "auto_fixed_count": len(result.auto_fixed),
            "issues": [
                {
                    "severity": i.severity.value,
                    "category": i.category,
                    "message": i.message,
                    "message_name": i.message_name,
                    "signal_name": i.signal_name,
                    "suggestion": i.suggestion,
                }
                for i in result.issues
            ],
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Report saved: {args.output}")

    # Exit code
    sys.exit(1 if result.has_errors else 0)


if __name__ == "__main__":
    main()
