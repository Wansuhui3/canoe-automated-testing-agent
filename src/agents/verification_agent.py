"""
Verification Sub-Agent

Orchestrates closed-loop verification by executing CANoe simulation,
comparing expected vs. actual bus data, and generating test reports.
"""

import logging
from pathlib import Path
from typing import Optional

from ..dbc.models import DBCModel
from ..verification.canoe_interface import CANoeConfig
from ..verification.simulator import SimulationController, VerificationStep, VerificationReport
from ..verification.comparator import ComparisonReport
from ..report.generator import ReportGenerator, ReportMetadata

logger = logging.getLogger(__name__)


class VerificationAgent:
    """
    Verification Sub-Agent: Final stage in the testing pipeline.

    Responsibilities:
    1. Execute CANoe simulation with generated CAPL scripts
    2. Capture bus data during simulation
    3. Compare expected signal values with actual bus data
    4. Generate standardized test reports (HTML/JSON)
    5. Report pass/fail status with detailed diagnostics

    Pipeline Flow:
        CAPL Scripts -> VerificationAgent -> Test Report

    This agent closes the loop by:
    - Loading the generated CAPL scripts into CANoe
    - Running the simulation
    - Reading back signal values from the bus
    - Comparing against expected values
    - Producing a comprehensive test report
    """

    def __init__(
        self,
        canoe_config: Optional[CANoeConfig] = None,
        tolerance_percent: float = 1.0,
    ) -> None:
        """
        Initialize the Verification Agent.

        Args:
            canoe_config: CANoe configuration
            tolerance_percent: Default tolerance for signal comparison
        """
        self.controller = SimulationController(
            canoe_config=canoe_config,
            tolerance_percent=tolerance_percent,
        )
        self.report_generator = ReportGenerator()
        self._last_report: Optional[VerificationReport] = None

    def execute_and_verify(
        self,
        capl_scripts: Optional[dict[str, str]] = None,
        verification_steps: Optional[list[VerificationStep]] = None,
        test_name: str = "automated_test",
        expected_signals: Optional[dict[str, float]] = None,
    ) -> VerificationReport:
        """
        Execute simulation and verify results.

        Args:
            capl_scripts: Generated CAPL scripts (signal_sim, diag_test)
            verification_steps: Custom verification steps
            test_name: Name for this test run
            expected_signals: Expected signal values for verification

        Returns:
            VerificationReport with complete results
        """
        logger.info(f"[Verification Agent] Starting test: {test_name}")

        # Build verification steps if not provided
        if verification_steps is None:
            verification_steps = self._build_default_steps(expected_signals or {})

        # Execute the test sequence
        self._last_report = self.controller.execute_test_sequence(
            steps=verification_steps,
            test_name=test_name,
        )

        logger.info(
            f"[Verification Agent] Test complete: "
            f"{self._last_report.steps_passed}/{self._last_report.steps_total} passed, "
            f"pass_rate={self._last_report.pass_rate:.1%}"
        )

        return self._last_report

    def generate_report(
        self,
        verification_report: Optional[VerificationReport] = None,
        output_dir: Optional[str] = None,
        metadata: Optional[ReportMetadata] = None,
    ) -> dict[str, str]:
        """
        Generate test reports in HTML and JSON formats.

        Args:
            verification_report: Verification results (uses last if None)
            output_dir: Directory to write report files
            metadata: Report metadata

        Returns:
            Dictionary: {"html": html_path, "json": json_path}
        """
        report = verification_report or self._last_report
        if report is None:
            raise ValueError("No verification report available. Run execute_and_verify() first.")

        if metadata:
            self.report_generator.metadata = metadata

        results = {}
        base_name = f"{report.test_name}_report"

        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            html_path = str(Path(output_dir) / f"{base_name}.html")
            json_path = str(Path(output_dir) / f"{base_name}.json")
        else:
            html_path = None
            json_path = None

        # Generate HTML report
        self.report_generator.generate_html(report, output_path=html_path)
        if html_path:
            results["html"] = html_path
            logger.info(f"[Verification Agent] HTML report: {html_path}")

        # Generate JSON report
        self.report_generator.generate_json(report, output_path=json_path)
        if json_path:
            results["json"] = json_path
            logger.info(f"[Verification Agent] JSON report: {json_path}")

        return results

    def _build_default_steps(
        self, expected_signals: dict[str, float]
    ) -> list[VerificationStep]:
        """Build default verification steps from expected signals."""
        steps = [
            VerificationStep(
                name="initialization",
                action="wait",
                wait_time_ms=2000,
            ),
        ]

        if expected_signals:
            steps.append(VerificationStep(
                name="signal_verification",
                action="verify",
                expected_signals=expected_signals,
            ))

        return steps

    @property
    def last_report(self) -> Optional[VerificationReport]:
        """Get the last verification report."""
        return self._last_report
