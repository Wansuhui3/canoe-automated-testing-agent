"""
Simulation Controller

Controls the execution of CANoe simulation for closed-loop testing,
coordinating message sending, data capture, and verification cycles.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .canoe_interface import CANoeInterface, CANoeConfig, SimulationResult
from .comparator import BusDataComparator, ComparisonReport

logger = logging.getLogger(__name__)


@dataclass
class VerificationStep:
    """A single verification step in the test sequence."""
    name: str
    action: str  # "send", "wait", "verify"
    message_id: Optional[int] = None
    data: Optional[list[int]] = None
    expected_signals: dict[str, float] = field(default_factory=dict)
    wait_time_ms: int = 1000


@dataclass
class VerificationReport:
    """Complete verification report for a test run."""
    test_name: str
    steps_total: int = 0
    steps_passed: int = 0
    steps_failed: int = 0
    comparison_report: Optional[ComparisonReport] = None
    simulation_result: Optional[SimulationResult] = None
    execution_time_ms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.steps_total == 0:
            return 0.0
        return self.steps_passed / self.steps_total

    @property
    def is_passed(self) -> bool:
        return self.steps_failed == 0 and self.steps_total > 0


class SimulationController:
    """
    Controls CANoe simulation for closed-loop test verification.

    Orchestrates the complete test lifecycle:
    1. Connect to CANoe and open configuration
    2. Start measurement/simulation
    3. Execute test steps (send, wait, verify)
    4. Collect and compare bus data
    5. Stop measurement and generate report
    """

    def __init__(
        self,
        canoe_config: Optional[CANoeConfig] = None,
        tolerance_percent: float = 1.0,
    ) -> None:
        """
        Initialize the simulation controller.

        Args:
            canoe_config: CANoe configuration settings
            tolerance_percent: Default tolerance for signal comparison
        """
        self.canoe = CANoeInterface(config=canoe_config)
        self.comparator = BusDataComparator(default_tolerance_percent=tolerance_percent)
        self._captured_data: dict[str, list[tuple[int, float]]] = {}  # signal -> [(time, value)]

    def execute_test_sequence(
        self,
        steps: list[VerificationStep],
        test_name: str = "automated_test",
    ) -> VerificationReport:
        """
        Execute a sequence of verification steps.

        Args:
            steps: Ordered list of verification steps
            test_name: Name for the test run

        Returns:
            VerificationReport with complete results
        """
        report = VerificationReport(test_name=test_name)
        start_time = time.time()

        # Connect to CANoe
        if not self.canoe.connect():
            report.errors.append("Failed to connect to CANoe")
            return report

        # Open configuration if specified
        if self.canoe._config:
            self.canoe.open_configuration()

        # Start measurement
        if not self.canoe.start_measurement():
            report.errors.append("Failed to start measurement")
            self.canoe.disconnect()
            return report

        try:
            for step in steps:
                report.steps_total += 1
                step_result = self._execute_step(step, report)
                if step_result:
                    report.steps_passed += 1
                else:
                    report.steps_failed += 1
        finally:
            # Stop measurement
            self.canoe.stop_measurement()
            self.canoe.disconnect()

        report.execution_time_ms = int((time.time() - start_time) * 1000)
        return report

    def _execute_step(self, step: VerificationStep, report: VerificationReport) -> bool:
        """Execute a single verification step."""
        logger.info(f"Executing step: {step.name} ({step.action})")

        if step.action == "send":
            if step.message_id is not None and step.data is not None:
                return self.canoe.send_can_message(step.message_id, step.data)
            return False

        elif step.action == "wait":
            if self.canoe.is_simulation_mode:
                logger.info(f"[SIM] Waiting {step.wait_time_ms}ms")
            else:
                time.sleep(step.wait_time_ms / 1000.0)
            return True

        elif step.action == "verify":
            if not step.expected_signals:
                return True

            # Read actual values
            actual_values: dict[str, Optional[float]] = {}
            for signal_full_name in step.expected_signals:
                parts = signal_full_name.split(".")
                if len(parts) == 2:
                    val = self.canoe.read_signal_value(parts[0], parts[1])
                else:
                    val = self.canoe.read_signal_value("", signal_full_name)
                actual_values[signal_full_name] = val

            # Compare
            comparison = self.comparator.compare(step.expected_signals, actual_values)
            report.comparison_report = comparison
            return comparison.pass_rate >= 0.8  # 80% pass threshold

        return False

    def quick_verify(
        self,
        expected_signals: dict[str, float],
        timeout_ms: int = 5000,
    ) -> ComparisonReport:
        """
        Quick verification: connect, read signals, compare, disconnect.

        Args:
            expected_signals: Expected signal values
            timeout_ms: Maximum wait time

        Returns:
            ComparisonReport
        """
        self.canoe.connect()
        if not self.canoe.is_measuring:
            self.canoe.start_measurement()

        # Read actual values
        actual_values: dict[str, Optional[float]] = {}
        for signal_full_name in expected_signals:
            parts = signal_full_name.split(".")
            if len(parts) == 2:
                val = self.canoe.read_signal_value(parts[0], parts[1])
            else:
                val = self.canoe.read_signal_value("", signal_full_name)
            actual_values[signal_full_name] = val

        self.canoe.stop_measurement()
        self.canoe.disconnect()

        return self.comparator.compare(expected_signals, actual_values)
