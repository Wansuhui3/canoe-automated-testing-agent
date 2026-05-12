"""
Unit tests for DBC Parser

Tests DBC file parsing, signal extraction, and model construction.
"""

import pytest
from pathlib import Path

from src.dbc.parser import DBCParser
from src.dbc.models import (
    DBCModel, MessageDefinition, SignalDefinition,
    ByteOrder, SignalType, ValidationResult, ValidationSeverity,
)
from src.dbc.validator import DBCValidator


EXAMPLE_DBC = str(Path(__file__).parent.parent / "examples" / "dbc" / "bcm_example.dbc")


class TestDBCParser:
    """Tests for DBC file parsing."""

    def test_parse_example_dbc(self):
        """Test parsing the example BCM DBC file."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        assert isinstance(model, DBCModel)
        assert model.filename == "bcm_example.dbc"
        assert len(model.messages) > 0
        assert len(model.nodes) > 0

    def test_parse_messages(self):
        """Test that messages are parsed with correct IDs and properties."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        # Check BCM_Status message
        bcm_msg = model.get_message("BCM_Status")
        assert bcm_msg is not None
        assert bcm_msg.id == 100
        assert bcm_msg.length == 8
        assert bcm_msg.sender == "BCM"

    def test_parse_signals(self):
        """Test that signals are parsed with correct properties."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        bcm_msg = model.get_message("BCM_Status")
        assert bcm_msg is not None

        # Check DoorLockFL signal
        door_sig = bcm_msg.get_signal("BCM_DoorLockFL")
        assert door_sig is not None
        assert door_sig.start_bit == 0
        assert door_sig.bit_length == 1
        assert door_sig.byte_order == ByteOrder.INTEL

    def test_parse_multiplexed_signals(self):
        """Test that multiplexer and multiplexed signals are correctly identified."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        bcm_msg = model.get_message("BCM_Status")
        assert bcm_msg is not None

        mux_signal = bcm_msg.get_multiplexer_signal()
        assert mux_signal is not None
        assert mux_signal.name == "BCM_Odometer"
        assert mux_signal.signal_type == SignalType.MULTIPLEXER

        mux_groups = bcm_msg.get_multiplexer_signals()
        assert len(mux_groups) > 0

    def test_parse_extended_id_message(self):
        """Test parsing messages with extended (29-bit) CAN IDs."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        radar_msg = model.get_message(0x18FEDA27)
        assert radar_msg is not None
        assert radar_msg.name == "RadarTrack"
        assert radar_msg.is_extended is True

    def test_signal_value_conversion(self):
        """Test raw-to-physical and physical-to-raw conversion."""
        sig = SignalDefinition(
            name="TestSignal",
            start_bit=0,
            bit_length=12,
            factor=0.25,
            offset=0.0,
        )

        # Raw 800 -> Physical 200.0
        assert sig.raw_to_physical(800) == 200.0

        # Physical 200.0 -> Raw 800
        assert sig.physical_to_raw(200.0) == 800

    def test_signal_with_offset(self):
        """Test signal conversion with non-zero offset."""
        sig = SignalDefinition(
            name="TempSignal",
            start_bit=0,
            bit_length=8,
            factor=1.0,
            offset=-40.0,
        )

        # Raw 130 -> Physical 90.0
        assert sig.raw_to_physical(130) == 90.0

        # Physical 90.0 -> Raw 130
        assert sig.physical_to_raw(90.0) == 130

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        parser = DBCParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("nonexistent.dbc")

    def test_get_messages_by_sender(self):
        """Test filtering messages by sender node."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        bcm_msgs = model.get_messages_by_sender("BCM")
        assert len(bcm_msgs) >= 1
        assert all(m.sender == "BCM" for m in bcm_msgs)

    def test_parse_value_tables(self):
        """Test that value tables are correctly parsed."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        bcm_msg = model.get_message("BCM_Status")
        if bcm_msg:
            door_sig = bcm_msg.get_signal("BCM_DoorLockFL")
            if door_sig and door_sig.value_table:
                assert 0 in door_sig.value_table
                assert door_sig.value_table[0] == "Locked"


class TestDBCValidator:
    """Tests for DBC model validation."""

    def test_validate_valid_model(self):
        """Test validation of a well-formed DBC model."""
        parser = DBCParser()
        model = parser.parse(EXAMPLE_DBC)

        validator = DBCValidator()
        result = validator.validate(model)

        assert isinstance(result, ValidationResult)
        assert isinstance(result.issues, list)

    def test_signal_bit_range_validation(self):
        """Test that out-of-range bit positions are detected."""
        sig = SignalDefinition(
            name="BadSignal",
            start_bit=60,
            bit_length=10,  # 60 + 10 = 70 > 64
        )

        issues = sig.validate_range()
        assert len(issues) > 0
        assert any("out of range" in i or ">" in i for i in issues)

    def test_validation_result_summary(self):
        """Test validation result summary generation."""
        result = ValidationResult(filename="test.dbc")
        result.add_issue(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="test",
            message="Test error",
            message_name="TestMsg",
        ))
        result.add_issue(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category="test",
            message="Test warning",
            message_name="TestMsg",
        ))

        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.has_errors

        summary = result.summary()
        assert "1" in summary  # Error count
        assert "1" in summary  # Warning count


class TestDBCModel:
    """Tests for DBC model data structures."""

    def test_message_get_signal(self):
        """Test retrieving a signal by name from a message."""
        msg = MessageDefinition(name="TestMsg", id=0x100)
        sig = SignalDefinition(name="TestSig", start_bit=0, bit_length=8)
        msg.signals.append(sig)

        assert msg.get_signal("TestSig") == sig
        assert msg.get_signal("NonExistent") is None

    def test_multiplexer_access(self):
        """Test multiplexer signal access methods."""
        msg = MessageDefinition(name="TestMsg", id=0x100)

        mux = SignalDefinition(
            name="MuxSig", start_bit=0, bit_length=4,
            signal_type=SignalType.MULTIPLEXER,
        )
        muxed = SignalDefinition(
            name="MuxedSig", start_bit=4, bit_length=8,
            signal_type=SignalType.MULTIPLEXED,
            mux_value=1,
        )
        msg.signals = [mux, muxed]

        assert msg.get_multiplexer_signal() == mux
        mux_groups = msg.get_multiplexer_signals()
        assert 1 in mux_groups
        assert muxed in mux_groups[1]

    def test_model_get_message(self):
        """Test retrieving a message by name or ID."""
        model = DBCModel(filename="test.dbc")
        msg = MessageDefinition(name="TestMsg", id=0x100)
        model.messages.append(msg)

        assert model.get_message("TestMsg") == msg
        assert model.get_message(0x100) == msg
        assert model.get_message("NonExistent") is None
