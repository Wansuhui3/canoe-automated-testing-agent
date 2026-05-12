"""
Batch Runner - End-to-end pipeline from DBC to test report.

Usage:
    python tools/batch_runner.py --dbc <dbc_file> --config <test_config> --output <output_dir>
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import DBCParseAgent, SignalReasonerAgent, CAPLGeneratorAgent, VerificationAgent
from src.report.generator import ReportMetadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CANoe Automated Testing Agent - Batch Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/batch_runner.py --dbc examples/dbc/bcm_example.dbc --config examples/config/bcm_test.yaml
  python tools/batch_runner.py --dbc my_database.dbc --config my_test.yaml --output ./reports
        """,
    )
    parser.add_argument(
        "--dbc", "-d",
        required=True,
        help="Path to the DBC file",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to the test configuration YAML file",
    )
    parser.add_argument(
        "--output", "-o",
        default="examples/output",
        help="Output directory for generated files (default: examples/output)",
    )
    parser.add_argument(
        "--spec", "-s",
        default="generic",
        help="OEM specification name or path (default: generic)",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Auto-fix DBC issues during parsing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    print("=" * 60)
    print("  CANoe Automated Testing Agent - Batch Runner")
    print("=" * 60)

    # ===== Stage 1: DBC Parse Agent =====
    print("\n📖 Stage 1: DBC Parse Agent")
    print("-" * 40)

    parse_agent = DBCParseAgent(auto_fix=args.auto_fix)
    model, validation = parse_agent.parse_and_validate(args.dbc)

    print(f"  Messages: {len(model.messages)}")
    print(f"  Nodes: {len(model.nodes)}")
    print(f"  Total signals: {sum(len(m.signals) for m in model.messages)}")
    print(f"  Validation: {validation.error_count} errors, {validation.warning_count} warnings")

    if validation.has_errors and not args.auto_fix:
        print("  ⚠️  DBC has validation errors. Use --auto-fix to resolve automatically.")

    # ===== Stage 2: Signal Reasoner Agent =====
    print("\n🧠 Stage 2: Signal Reasoner Agent")
    print("-" * 40)

    reasoner_agent = SignalReasonerAgent()
    dep_graph = reasoner_agent.analyze(model)

    print(f"  Signal nodes: {dep_graph.graph.number_of_nodes()}")
    print(f"  Dependency edges: {dep_graph.graph.number_of_edges()}")

    mux_sequences = reasoner_agent.get_mux_switch_sequences(model)
    if mux_sequences:
        for msg_name, seq in mux_sequences.items():
            print(f"  Mux sequence ({msg_name}): {seq}")

    # ===== Stage 3: CAPL Generator Agent =====
    print("\n📝 Stage 3: CAPL Generator Agent")
    print("-" * 40)

    # Determine spec
    spec_path = args.spec if Path(args.spec).exists() else None
    spec_name = args.spec if not spec_path else "generic"

    capl_agent = CAPLGeneratorAgent(spec=spec_path, spec_name=spec_name)
    scripts = capl_agent.generate_all(
        dbc_model=model,
        dep_graph=dep_graph,
        output_dir=args.output,
        services=None,
        security_seed=0xA5B6,
    )

    for script_type, content in scripts.items():
        line_count = len(content.splitlines())
        print(f"  {script_type}: {line_count} lines")

    # ===== Stage 4: Verification Agent =====
    print("\n🔄 Stage 4: Verification Agent")
    print("-" * 40)

    verify_agent = VerificationAgent()
    report = verify_agent.execute_and_verify(
        capl_scripts=scripts,
        test_name=f"{model.filename}_automated_test",
    )

    print(f"  Steps: {report.steps_passed}/{report.steps_total} passed")
    print(f"  Pass rate: {report.pass_rate:.1%}")
    print(f"  Execution time: {report.execution_time_ms}ms")

    # Generate reports
    metadata = ReportMetadata(
        project_name="CANoe Automated Testing",
        test_target=model.filename,
        dbc_filename=model.filename,
        oem_spec=spec_name,
    )

    report_paths = verify_agent.generate_report(
        output_dir=args.output,
        metadata=metadata,
    )

    if report_paths:
        print("\n📄 Generated Reports:")
        for fmt, path in report_paths.items():
            print(f"  {fmt.upper()}: {path}")

    # Summary
    print("\n" + "=" * 60)
    if report.is_passed:
        print("  ✅ ALL TESTS PASSED")
    else:
        print(f"  ❌ TESTS FAILED (pass rate: {report.pass_rate:.1%})")
    print("=" * 60)

    sys.exit(0 if report.is_passed else 1)


if __name__ == "__main__":
    main()
