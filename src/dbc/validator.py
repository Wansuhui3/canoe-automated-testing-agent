"""
DBC Signal Validator

Validates DBC file definitions for common issues including:
- Signal bit position overlaps
- Byte order inconsistencies
- Multiplexing configuration errors
- Non-standard naming conventions
- Factor/offset/range inconsistencies
"""

from .models import (
    DBCModel, MessageDefinition, SignalDefinition,
    ValidationResult, ValidationIssue, ValidationSeverity, SignalType, ByteOrder,
)


class DBCValidator:
    """
    Validates DBC model definitions and identifies issues.

    The validator performs multi-level checks:
    1. Per-signal validation (bit range, naming, factor/offset)
    2. Per-message validation (signal overlap, multiplexing consistency)
    3. Cross-message validation (ID conflicts, naming consistency)
    """

    def __init__(self, auto_fix: bool = False) -> None:
        """
        Initialize the validator.

        Args:
            auto_fix: If True, automatically fix fixable issues and record them
        """
        self.auto_fix = auto_fix

    def validate(self, dbc_model: DBCModel) -> ValidationResult:
        """
        Validate a DBC model and return all found issues.

        Args:
            dbc_model: The parsed DBC model to validate

        Returns:
            ValidationResult containing all issues and auto-fix records
        """
        result = ValidationResult(filename=dbc_model.filename)

        # Per-message validation
        for msg in dbc_model.messages:
            self._validate_message(msg, result)

        # Cross-message validation
        self._validate_cross_message(dbc_model, result)

        return result

    def _validate_message(self, msg: MessageDefinition, result: ValidationResult) -> None:
        """Validate a single message and its signals."""
        # Check message ID validity
        if msg.id < 0 or msg.id > 0x1FFFFFFF:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="message_id",
                message=f"Invalid message ID: 0x{msg.id:X}",
                message_name=msg.name,
                suggestion="Ensure message ID is within valid CAN ID range",
            ))

        # Check DLC (data length code)
        if msg.length not in (1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64):
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="dlc",
                message=f"Non-standard DLC: {msg.length} bytes",
                message_name=msg.name,
                suggestion="Standard CAN DLC: 1-8; CAN FD: 12,16,20,24,32,48,64",
            ))

        # Per-signal validation
        for sig in msg.signals:
            self._validate_signal(msg, sig, result)

        # Signal overlap detection
        self._check_signal_overlap(msg, result)

        # Multiplexing validation
        self._validate_multiplexing(msg, result)

    def _validate_signal(
        self, msg: MessageDefinition, sig: SignalDefinition, result: ValidationResult
    ) -> None:
        """Validate a single signal definition."""
        # Bit range check
        range_issues = sig.validate_range()
        for issue in range_issues:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="bit_range",
                message=issue,
                message_name=msg.name,
                signal_name=sig.name,
            ))

        # Byte order validation for specific bit ranges
        if sig.byte_order == ByteOrder.MOTOROLA and sig.bit_length > 1:
            # Motorola byte order: start_bit should be the MSB position
            # Check if the signal crosses byte boundaries correctly
            start_byte = sig.start_bit // 8
            end_bit = self._calculate_motorola_end_bit(sig.start_bit, sig.bit_length)
            end_byte = end_bit // 8
            if end_byte - start_byte + 1 > msg.length:
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="byte_order",
                    message=f"Motorola signal crosses beyond message DLC "
                            f"(bytes {start_byte}-{end_byte}, DLC={msg.length})",
                    message_name=msg.name,
                    signal_name=sig.name,
                    suggestion=f"Increase message DLC to at least {end_byte + 1}",
                ))

        # Factor/offset validation
        if sig.factor == 0:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="factor",
                message="Factor cannot be zero (division by zero in conversion)",
                message_name=msg.name,
                signal_name=sig.name,
                suggestion="Set factor to at least 1 or appropriate scaling value",
            ))

        # Min/max vs. raw range consistency
        raw_min = sig.physical_to_raw(sig.min_val)
        raw_max = sig.physical_to_raw(sig.max_val)
        max_raw_value = (1 << sig.bit_length) - 1
        if raw_max > max_raw_value or raw_min < 0:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="range_mismatch",
                message=f"Physical range [{sig.min_val}, {sig.max_val}] maps to "
                        f"raw [{raw_min}, {raw_max}], exceeding {sig.bit_length}-bit range [0, {max_raw_value}]",
                message_name=msg.name,
                signal_name=sig.name,
            ))

        # Naming convention check
        self._check_naming_convention(msg, sig, result)

    def _check_naming_convention(
        self, msg: MessageDefinition, sig: SignalDefinition, result: ValidationResult
    ) -> None:
        """Check signal and message naming conventions."""
        # Check for spaces in signal names (not allowed in DBC)
        if " " in sig.name:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="naming",
                message="Signal name contains spaces (invalid in DBC format)",
                message_name=msg.name,
                signal_name=sig.name,
                suggestion=f"Replace spaces with underscores: {sig.name.replace(' ', '_')}",
            ))

        # Check for duplicate signal names within a message
        signal_names = [s.name for s in msg.signals]
        if signal_names.count(sig.name) > 1:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="naming",
                message=f"Duplicate signal name: {sig.name}",
                message_name=msg.name,
                signal_name=sig.name,
            ))

    def _check_signal_overlap(
        self, msg: MessageDefinition, result: ValidationResult
    ) -> None:
        """Check for overlapping bit positions between signals."""
        # Build bit occupancy map for each mux group
        normal_signals = [s for s in msg.signals if s.signal_type in
                          (SignalType.NORMAL, SignalType.MULTIPLEXER)]
        mux_groups = msg.get_multiplexer_signals()

        # Check normal signals for overlap
        self._check_overlap_in_group(msg, normal_signals, result, "normal")

        # Check each mux group for overlap
        for mux_val, mux_signals in mux_groups.items():
            self._check_overlap_in_group(msg, mux_signals, result, f"mux={mux_val}")

    def _check_overlap_in_group(
        self,
        msg: MessageDefinition,
        signals: list[SignalDefinition],
        result: ValidationResult,
        group_label: str,
    ) -> None:
        """Check for bit overlap within a group of signals."""
        occupied: dict[int, str] = {}  # bit_position -> signal_name

        for sig in signals:
            bit_positions = self._get_occupied_bits(sig)
            for bit in bit_positions:
                if bit in occupied:
                    result.add_issue(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="bit_overlap",
                        message=f"Bit {bit} occupied by both '{occupied[bit]}' and '{sig.name}' ({group_label})",
                        message_name=msg.name,
                        signal_name=sig.name,
                        suggestion="Adjust start_bit or bit_length to eliminate overlap",
                    ))
                else:
                    occupied[bit] = sig.name

    def _validate_multiplexing(
        self, msg: MessageDefinition, result: ValidationResult
    ) -> None:
        """Validate multiplexing configuration consistency."""
        mux_signal = msg.get_multiplexer_signal()
        mux_signals = [s for s in msg.signals if s.signal_type == SignalType.MULTIPLEXED]

        if mux_signals and not mux_signal:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="multiplexing",
                message=f"Multiplexed signals exist but no multiplexer (M) signal defined",
                message_name=msg.name,
                suggestion="Add a multiplexer signal (M indicator) to define the switch",
            ))

        if mux_signal and not mux_signals:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="multiplexing",
                message=f"Multiplexer signal '{mux_signal.name}' defined but no multiplexed signals",
                message_name=msg.name,
                signal_name=mux_signal.name,
            ))

        # Check that mux signal has appropriate bit length
        if mux_signal and mux_signal.bit_length > 8:
            result.add_issue(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="multiplexing",
                message=f"Multiplexer signal bit_length={mux_signal.bit_length} is unusually large",
                message_name=msg.name,
                signal_name=mux_signal.name,
                suggestion="Typical mux signals use 1-4 bits",
            ))

    def _validate_cross_message(
        self, dbc_model: DBCModel, result: ValidationResult
    ) -> None:
        """Validate cross-message consistency."""
        # Check for duplicate message IDs
        seen_ids: dict[int, str] = {}
        for msg in dbc_model.messages:
            if msg.id in seen_ids:
                result.add_issue(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="duplicate_id",
                    message=f"Duplicate message ID 0x{msg.id:X}: '{seen_ids[msg.id]}' and '{msg.name}'",
                    message_name=msg.name,
                    suggestion="Ensure each message has a unique CAN ID",
                ))
            else:
                seen_ids[msg.id] = msg.name

    @staticmethod
    def _calculate_motorola_end_bit(start_bit: int, bit_length: int) -> int:
        """
        Calculate the end bit position for a Motorola (big-endian) signal.

        Motorola bit numbering follows the OER (Over-the-Edge Representation)
        convention used in DBC files.
        """
        byte_idx = start_bit // 8
        bit_in_byte = 7 - (start_bit % 8)  # MSB first within byte
        remaining = bit_length - 1
        current_byte = byte_idx

        while remaining > 0:
            bits_in_this_byte = min(remaining, bit_in_byte + 1)
            remaining -= bits_in_this_byte
            if remaining > 0:
                current_byte += 1
                bit_in_byte = 7  # Next byte starts from MSB
            else:
                bit_in_byte -= bits_in_this_byte - 1

        return current_byte * 8 + (7 - bit_in_byte)

    @staticmethod
    def _get_occupied_bits(sig: SignalDefinition) -> list[int]:
        """Get all bit positions occupied by a signal."""
        bits = []
        if sig.byte_order == ByteOrder.INTEL:
            # Intel: contiguous from start_bit
            for i in range(sig.bit_length):
                bits.append(sig.start_bit + i)
        else:
            # Motorola: non-contiguous, byte-jumping
            # Simplified: use start_bit to end range
            end_bit = DBCValidator._calculate_motorola_end_bit(sig.start_bit, sig.bit_length)
            # This is a simplified model; real Motorola layout is more complex
            for byte_idx in range(sig.start_bit // 8, end_bit // 8 + 1):
                for bit_in_byte in range(8):
                    bit_pos = byte_idx * 8 + bit_in_byte
                    if sig.start_bit <= bit_pos <= end_bit:
                        bits.append(bit_pos)
        return bits
