"""
Bus Data Comparator

Compares expected signal values with actual bus data captured
during CANoe simulation, identifying mismatches and generating
comparison reports.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ComparisonResult(Enum):
    """Result of a single signal comparison."""
    MATCH = "match"
    MISMATCH = "mismatch"
    TOLERANCE_EXCEEDED = "tolerance_exceeded"
    NO_DATA = "no_data"


@dataclass
class SignalComparison:
    """Result of comparing a single signal value."""
    signal_name: str
    message_name: str
    expected_value: float
    actual_value: Optional[float]
    tolerance_percent: float
    result: ComparisonResult
    deviation_percent: float = 0.0
    timestamp_ms: int = 0

    def __str__(self) -> str:
        if self.result == ComparisonResult.NO_DATA:
            return f"[NO_DATA] {self.message_name}.{self.signal_name}"
        status = self.result.value.upper()
        return (
            f"[{status}] {self.message_name}.{self.signal_name}: "
            f"expected={self.expected_value:.4f}, actual={self.actual_value:.4f}, "
            f"deviation={self.deviation_percent:.2f}%"
        )


@dataclass
class ComparisonReport:
    """Aggregated comparison report for all signals."""
    total_signals: int = 0
    matches: int = 0
    mismatches: int = 0
    tolerance_exceeded: int = 0
    no_data: int = 0
    signal_results: list[SignalComparison] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_signals == 0:
            return 0.0
        return self.matches / self.total_signals

    @property
    def fail_rate(self) -> float:
        return 1.0 - self.pass_rate

    def add_result(self, result: SignalComparison) -> None:
        self.signal_results.append(result)
        self.total_signals += 1
        if result.result == ComparisonResult.MATCH:
            self.matches += 1
        elif result.result == ComparisonResult.MISMATCH:
            self.mismatches += 1
        elif result.result == ComparisonResult.TOLERANCE_EXCEEDED:
            self.tolerance_exceeded += 1
        elif result.result == ComparisonResult.NO_DATA:
            self.no_data += 1

    def summary(self) -> str:
        lines = [
            "=== Signal Comparison Report ===",
            f"Total: {self.total_signals}",
            f"  Match: {self.matches} ({self.matches/self.total_signals*100:.1f}%)" if self.total_signals else "  Match: 0",
            f"  Mismatch: {self.mismatches}",
            f"  Tolerance Exceeded: {self.tolerance_exceeded}",
            f"  No Data: {self.no_data}",
            f"Pass Rate: {self.pass_rate:.1%}",
        ]
        if self.mismatches > 0 or self.tolerance_exceeded > 0:
            lines.append("")
            lines.append("Failed comparisons:")
            for r in self.signal_results:
                if r.result in (ComparisonResult.MISMATCH, ComparisonResult.TOLERANCE_EXCEEDED):
                    lines.append(f"  {r}")
        return "\n".join(lines)


class BusDataComparator:
    """
    Compares expected signal values with actual bus data.

    Supports configurable tolerance for floating-point comparisons
    and generates detailed comparison reports.
    """

    def __init__(self, default_tolerance_percent: float = 1.0) -> None:
        """
        Initialize the comparator.

        Args:
            default_tolerance_percent: Default tolerance as percentage (1.0 = 1%)
        """
        self.default_tolerance_percent = default_tolerance_percent

    def compare(
        self,
        expected: dict[str, float],  # signal_full_name -> expected_value
        actual: dict[str, Optional[float]],  # signal_full_name -> actual_value
        tolerances: Optional[dict[str, float]] = None,  # per-signal tolerance override
    ) -> ComparisonReport:
        """
        Compare expected vs. actual signal values.

        Args:
            expected: Dictionary of signal full names to expected values
            actual: Dictionary of signal full names to actual values (None = no data)
            tolerances: Per-signal tolerance overrides (optional)

        Returns:
            ComparisonReport with detailed results
        """
        report = ComparisonReport()
        tolerances = tolerances or {}

        for full_name, expected_val in expected.items():
            tolerance = tolerances.get(full_name, self.default_tolerance_percent)
            actual_val = actual.get(full_name)

            # Parse message.signal format
            parts = full_name.split(".")
            msg_name = parts[0] if len(parts) > 1 else ""
            sig_name = parts[1] if len(parts) > 1 else full_name

            if actual_val is None:
                report.add_result(SignalComparison(
                    signal_name=sig_name,
                    message_name=msg_name,
                    expected_value=expected_val,
                    actual_value=None,
                    tolerance_percent=tolerance,
                    result=ComparisonResult.NO_DATA,
                ))
                continue

            # Calculate deviation
            if expected_val != 0:
                deviation_percent = abs(actual_val - expected_val) / abs(expected_val) * 100
            else:
                deviation_percent = 0.0 if actual_val == 0 else float("inf")

            # Determine result
            if deviation_percent == 0:
                result = ComparisonResult.MATCH
            elif deviation_percent <= tolerance:
                result = ComparisonResult.MATCH  # Within tolerance = match
            else:
                result = ComparisonResult.TOLERANCE_EXCEEDED

            report.add_result(SignalComparison(
                signal_name=sig_name,
                message_name=msg_name,
                expected_value=expected_val,
                actual_value=actual_val,
                tolerance_percent=tolerance,
                result=result,
                deviation_percent=deviation_percent,
            ))

        return report

    def compare_raw_values(
        self,
        message_name: str,
        signal_name: str,
        expected_raw: int,
        actual_raw: Optional[int],
        tolerance_percent: float = 0.0,
    ) -> SignalComparison:
        """
        Compare a single signal's raw value.

        Args:
            message_name: CAN message name
            signal_name: Signal name
            expected_raw: Expected raw value
            actual_raw: Actual raw value from bus
            tolerance_percent: Tolerance percentage

        Returns:
            SignalComparison result
        """
        if actual_raw is None:
            return SignalComparison(
                signal_name=signal_name,
                message_name=message_name,
                expected_value=float(expected_raw),
                actual_value=None,
                tolerance_percent=tolerance_percent,
                result=ComparisonResult.NO_DATA,
            )

        deviation = 0.0
        if expected_raw != 0:
            deviation = abs(actual_raw - expected_raw) / abs(expected_raw) * 100

        result = ComparisonResult.MATCH if deviation <= tolerance_percent else ComparisonResult.TOLERANCE_EXCEEDED

        return SignalComparison(
            signal_name=signal_name,
            message_name=message_name,
            expected_value=float(expected_raw),
            actual_value=float(actual_raw),
            tolerance_percent=tolerance_percent,
            result=result,
            deviation_percent=deviation,
        )
