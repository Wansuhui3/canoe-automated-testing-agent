"""
Unit tests for Verification Module

Tests bus data comparison and verification reporting.
"""

import pytest

from src.verification.comparator import (
    BusDataComparator, ComparisonReport, ComparisonResult, SignalComparison,
)
from src.verification.simulator import VerificationStep, VerificationReport
from src.verification.canoe_interface import CANoeInterface, CANoeConfig
from src.report.generator import ReportGenerator, ReportMetadata


class TestBusDataComparator:
    """Tests for bus data comparison."""

    def test_match_comparison(self):
        """Test comparison where all signals match."""
        comparator = BusDataComparator(default_tolerance_percent=1.0)
        expected = {"Msg1.Sig1": 100.0, "Msg1.Sig2": 200.0}
        actual = {"Msg1.Sig1": 100.0, "Msg1.Sig2": 200.0}

        report = comparator.compare(expected, actual)
        assert report.pass_rate == 1.0
        assert report.matches == 2
        assert report.mismatches == 0

    def test_tolerance_exceeded(self):
        """Test comparison where deviation exceeds tolerance."""
        comparator = BusDataComparator(default_tolerance_percent=1.0)
        expected = {"Msg1.Sig1": 100.0}
        actual = {"Msg1.Sig1": 105.0}  # 5% deviation

        report = comparator.compare(expected, actual)
        assert report.tolerance_exceeded == 1

    def test_within_tolerance(self):
        """Test comparison where deviation is within tolerance."""
        comparator = BusDataComparator(default_tolerance_percent=5.0)
        expected = {"Msg1.Sig1": 100.0}
        actual = {"Msg1.Sig1": 102.0}  # 2% deviation, within 5%

        report = comparator.compare(expected, actual)
        assert report.matches == 1

    def test_no_data(self):
        """Test comparison where actual data is missing."""
        comparator = BusDataComparator()
        expected = {"Msg1.Sig1": 100.0}
        actual = {"Msg1.Sig1": None}

        report = comparator.compare(expected, actual)
        assert report.no_data == 1

    def test_mixed_results(self):
        """Test comparison with mixed results."""
        comparator = BusDataComparator(default_tolerance_percent=1.0)
        expected = {"Msg1.Sig1": 100.0, "Msg1.Sig2": 200.0, "Msg1.Sig3": 300.0}
        actual = {"Msg1.Sig1": 100.0, "Msg1.Sig2": None, "Msg1.Sig3": 310.0}

        report = comparator.compare(expected, actual)
        assert report.matches == 1
        assert report.no_data == 1
        assert report.tolerance_exceeded == 1

    def test_custom_tolerance_per_signal(self):
        """Test per-signal tolerance override."""
        comparator = BusDataComparator(default_tolerance_percent=1.0)
        expected = {"Msg1.Sig1": 100.0, "Msg1.Sig2": 200.0}
        actual = {"Msg1.Sig1": 105.0, "Msg1.Sig2": 205.0}

        # Sig1: 5% with 1% tolerance -> fail
        # Sig2: 2.5% with 10% tolerance -> pass
        report = comparator.compare(expected, actual, tolerances={"Msg1.Sig2": 10.0})
        assert report.tolerance_exceeded == 1
        assert report.matches == 1

    def test_comparison_summary(self):
        """Test comparison report summary generation."""
        comparator = BusDataComparator()
        expected = {"Msg1.Sig1": 100.0}
        actual = {"Msg1.Sig1": 100.0}

        report = comparator.compare(expected, actual)
        summary = report.summary()
        assert "100.0%" in summary


def _canoe_com_available() -> bool:
    """Check if CANoe COM is available (CANoe installed and running)."""
    try:
        import win32com.client
        app = win32com.client.Dispatch("CANoe.Application")
        return True
    except Exception:
        return False


_CANOE_AVAILABLE = _canoe_com_available()


class TestCANoeInterface:
    """Tests for CANoe interface (simulation mode).

    These tests require CANoe to NOT be running so the interface
    falls back to simulation mode. If CANoe is installed and its
    COM server responds, the tests are skipped.
    """

    @pytest.mark.skipif(_CANOE_AVAILABLE, reason="CANoe COM available - simulation mode test not applicable")
    def test_connect_simulation_mode(self):
        """Test connecting in simulation mode."""
        interface = CANoeInterface()
        result = interface.connect()
        assert result is True
        assert interface.is_simulation_mode is True

    def test_connect_always_succeeds(self):
        """Test that connect always succeeds (simulation or real)."""
        interface = CANoeInterface()
        result = interface.connect()
        assert result is True
        assert interface.is_connected is True

    @pytest.mark.skipif(_CANOE_AVAILABLE, reason="CANoe COM available - simulation mode test not applicable")
    def test_send_message_simulation(self):
        """Test sending a message in simulation mode."""
        interface = CANoeInterface()
        interface.connect()
        if interface.is_simulation_mode:
            result = interface.send_can_message(0x100, [0x01, 0x02, 0x03])
            assert result is True

    @pytest.mark.skipif(_CANOE_AVAILABLE, reason="CANoe COM available - simulation mode test not applicable")
    def test_read_signal_simulation(self):
        """Test reading a signal in simulation mode."""
        interface = CANoeInterface()
        interface.connect()
        if interface.is_simulation_mode:
            value = interface.read_signal_value("TestMsg", "TestSig")
            assert value is not None


class TestVerificationReport:
    """Tests for verification report data structures."""

    def test_pass_rate(self):
        """Test pass rate calculation."""
        report = VerificationReport(test_name="test")
        report.steps_total = 10
        report.steps_passed = 8
        report.steps_failed = 2

        assert report.pass_rate == 0.8
        assert not report.is_passed

    def test_all_passed(self):
        """Test when all steps pass."""
        report = VerificationReport(test_name="test")
        report.steps_total = 5
        report.steps_passed = 5
        report.steps_failed = 0

        assert report.pass_rate == 1.0
        assert report.is_passed

    def test_empty_report(self):
        """Test empty report edge case."""
        report = VerificationReport(test_name="test")
        assert report.pass_rate == 0.0
        assert not report.is_passed


class TestReportGenerator:
    """Tests for HTML/JSON report generation."""

    def test_generate_html(self):
        """Test HTML report generation."""
        gen = ReportGenerator(metadata=ReportMetadata(
            project_name="test", test_target="BCM"
        ))

        report = VerificationReport(test_name="test")
        report.steps_total = 3
        report.steps_passed = 2
        report.steps_failed = 1

        html = gen.generate_html(report)
        assert "<html" in html
        assert "test" in html
        assert "PASSED" in html or "FAILED" in html

    def test_generate_json(self):
        """Test JSON report generation."""
        gen = ReportGenerator()

        report = VerificationReport(test_name="test")
        report.steps_total = 3
        report.steps_passed = 3
        report.steps_failed = 0

        data = gen.generate_json(report)
        assert data["verification"]["test_name"] == "test"
        assert data["verification"]["pass_rate"] == 1.0
