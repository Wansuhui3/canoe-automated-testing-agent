"""
CANoe Automated Testing Agent - Main Entry Point

Provides a simple API for running the complete automated testing pipeline.

Example usage:
    from src.main import run_pipeline

    report = run_pipeline(
        dbc_path="examples/dbc/bcm_example.dbc",
        spec_name="bcm_simplified",
    )
"""

import logging
from pathlib import Path
from typing import Optional

from .agents import DBCParseAgent, SignalReasonerAgent, CAPLGeneratorAgent, VerificationAgent
from .report.generator import ReportGenerator, ReportMetadata
from .verification.simulator import VerificationReport

logger = logging.getLogger(__name__)


def run_pipeline(
    dbc_path: str,
    spec_name: str = "generic",
    spec_path: Optional[str] = None,
    target_node: Optional[str] = None,
    services: Optional[list[int]] = None,
    security_seed: int = 0xA5B6,
    output_dir: Optional[str] = None,
    auto_fix: bool = False,
    tolerance_percent: float = 1.0,
) -> VerificationReport:
    """
    Run the complete automated testing pipeline.

    Pipeline:
        DBC Parse -> Signal Reasoning -> CAPL Generation -> Verification -> Report

    Args:
        dbc_path: Path to the DBC file
        spec_name: OEM specification name (default: "generic")
        spec_path: Path to OEM spec YAML (overrides spec_name)
        target_node: Only generate for this sender node
        services: UDS service IDs to test (None = all known)
        security_seed: Security seed for simplified testing
        output_dir: Output directory for reports and scripts
        auto_fix: Auto-fix DBC issues
        tolerance_percent: Signal comparison tolerance

    Returns:
        VerificationReport with complete test results
    """
    # Stage 1: DBC Parse
    logger.info("Stage 1: DBC Parse Agent")
    parse_agent = DBCParseAgent(auto_fix=auto_fix)
    model, validation = parse_agent.parse_and_validate(dbc_path)
    logger.info(f"Parsed {len(model.messages)} messages, validation: {validation.summary()}")

    # Stage 2: Signal Reasoning
    logger.info("Stage 2: Signal Reasoner Agent")
    reasoner = SignalReasonerAgent()
    dep_graph = reasoner.analyze(model)
    logger.info(f"Dependency graph: {dep_graph.graph.number_of_nodes()} nodes")

    # Stage 3: CAPL Generation
    logger.info("Stage 3: CAPL Generator Agent")
    capl_agent = CAPLGeneratorAgent(spec=spec_path, spec_name=spec_name)
    scripts = capl_agent.generate_all(
        dbc_model=model,
        dep_graph=dep_graph,
        output_dir=output_dir,
        services=services,
        security_seed=security_seed,
    )

    # Stage 4: Verification
    logger.info("Stage 4: Verification Agent")
    verify_agent = VerificationAgent(tolerance_percent=tolerance_percent)
    report = verify_agent.execute_and_verify(
        capl_scripts=scripts,
        test_name=f"{model.filename}_automated_test",
    )

    # Generate reports
    if output_dir:
        metadata = ReportMetadata(
            project_name="CANoe Automated Testing",
            test_target=model.filename,
            dbc_filename=model.filename,
            oem_spec=spec_name,
        )
        verify_agent.generate_report(output_dir=output_dir, metadata=metadata)

    return report


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m src.main <dbc_path> [spec_name]")
        sys.exit(1)

    dbc = sys.argv[1]
    spec = sys.argv[2] if len(sys.argv) > 2 else "generic"

    result = run_pipeline(dbc_path=dbc, spec_name=spec)
    print(f"\nResult: {'PASSED' if result.is_passed else 'FAILED'} ({result.pass_rate:.1%})")
