"""
DBC Data Models

Defines the data structures for DBC file parsing results,
including messages, signals, value tables, and nodes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ByteOrder(Enum):
    """Signal byte order (endianness)."""
    MOTOROLA = "motorola"  # Big-endian, MSB first
    INTEL = "intel"        # Little-endian, LSB first


class SignalType(Enum):
    """Signal type classification."""
    NORMAL = "normal"
    MULTIPLEXER = "multiplexer"  # Multiplexer switch signal
    MULTIPLEXED = "multiplexed"  # Multiplexed signal (controlled by mux)


class ValidationSeverity(Enum):
    """Validation issue severity levels."""
    ERROR = "error"        # Must fix - will cause runtime issues
    WARNING = "warning"    # Should fix - may cause unexpected behavior
    INFO = "info"          # Good to know - style/best practice


@dataclass
class SignalDefinition:
    """
    Signal definition within a CAN message.

    Attributes:
        name: Signal name (e.g., "EngineSpeed")
        start_bit: Bit position where signal starts (0-63 for classic CAN)
        bit_length: Signal length in bits
        byte_order: Motorola (big-endian) or Intel (little-endian)
        factor: Scaling factor for raw-to-physical conversion
        offset: Offset for raw-to-physical conversion
        min_val: Minimum physical value
        max_val: Maximum physical value
        unit: Physical unit string (e.g., "rpm", "km/h")
        signal_type: Normal, Multiplexer, or Multiplexed
        mux_value: Multiplexer value (only for MULTIPLEXED type)
        comment: Signal description/comment
        value_table: Mapping of raw values to descriptions
    """
    name: str
    start_bit: int
    bit_length: int
    byte_order: ByteOrder = ByteOrder.INTEL
    factor: float = 1.0
    offset: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    unit: str = ""
    signal_type: SignalType = SignalType.NORMAL
    mux_value: Optional[int] = None
    comment: str = ""
    value_table: dict[int, str] = field(default_factory=dict)

    def raw_to_physical(self, raw_value: int) -> float:
        """Convert raw CAN value to physical value."""
        return raw_value * self.factor + self.offset

    def physical_to_raw(self, physical_value: float) -> int:
        """Convert physical value to raw CAN value."""
        return int((physical_value - self.offset) / self.factor)

    def validate_range(self) -> list[str]:
        """Validate signal bit position and length constraints."""
        issues = []
        if self.start_bit < 0 or self.start_bit > 63:
            issues.append(f"Signal {self.name}: start_bit={self.start_bit} out of range [0, 63]")
        if self.bit_length <= 0:
            issues.append(f"Signal {self.name}: bit_length={self.bit_length} must be positive")
        if self.start_bit + self.bit_length > 64:
            issues.append(
                f"Signal {self.name}: start_bit({self.start_bit}) + "
                f"bit_length({self.bit_length}) = {self.start_bit + self.bit_length} > 64"
            )
        return issues


@dataclass
class MessageDefinition:
    """
    CAN message definition.

    Attributes:
        name: Message name (e.g., "EngineData")
        id: CAN message ID (e.g., 0x123)
        length: Message data length in bytes (typically 8 for classic CAN)
        sender: Sending node name
        signals: List of signal definitions within this message
        comment: Message description/comment
        is_extended: Whether this uses extended (29-bit) CAN ID
        cycle_time: Message cycle time in milliseconds (0 = event-driven)
    """
    name: str
    id: int
    length: int = 8
    sender: str = ""
    signals: list[SignalDefinition] = field(default_factory=list)
    comment: str = ""
    is_extended: bool = False
    cycle_time: int = 0

    def get_signal(self, signal_name: str) -> Optional[SignalDefinition]:
        """Get a signal by name."""
        for sig in self.signals:
            if sig.name == signal_name:
                return sig
        return None

    def get_multiplexer_signals(self) -> dict[int, list[SignalDefinition]]:
        """Get multiplexed signals grouped by mux value."""
        mux_groups: dict[int, list[SignalDefinition]] = {}
        for sig in self.signals:
            if sig.signal_type == SignalType.MULTIPLEXED and sig.mux_value is not None:
                if sig.mux_value not in mux_groups:
                    mux_groups[sig.mux_value] = []
                mux_groups[sig.mux_value].append(sig)
        return mux_groups

    def get_multiplexer_signal(self) -> Optional[SignalDefinition]:
        """Get the multiplexer switch signal (if any)."""
        for sig in self.signals:
            if sig.signal_type == SignalType.MULTIPLEXER:
                return sig
        return None


@dataclass
class NodeDefinition:
    """Node (ECU) definition in the DBC."""
    name: str
    comment: str = ""


@dataclass
class DBCModel:
    """
    Complete DBC file model.

    Contains all parsed information from a DBC file.
    """
    filename: str
    version: str = ""
    nodes: list[NodeDefinition] = field(default_factory=list)
    messages: list[MessageDefinition] = field(default_factory=list)
    value_tables: dict[str, dict[int, str]] = field(default_factory=dict)

    def get_message(self, name_or_id) -> Optional[MessageDefinition]:
        """Get a message by name (str) or ID (int)."""
        for msg in self.messages:
            if isinstance(name_or_id, str) and msg.name == name_or_id:
                return msg
            if isinstance(name_or_id, int) and msg.id == name_or_id:
                return msg
        return None

    def get_messages_by_sender(self, sender: str) -> list[MessageDefinition]:
        """Get all messages sent by a specific node."""
        return [msg for msg in self.messages if msg.sender == sender]


@dataclass
class ValidationIssue:
    """
    Validation issue found during DBC analysis.

    Attributes:
        severity: Error, Warning, or Info
        category: Issue category (e.g., "bit_overlap", "byte_order", "multiplexing")
        message: Human-readable description
        message_name: Affected CAN message name
        signal_name: Affected signal name (if applicable)
        suggestion: Suggested fix (if applicable)
    """
    severity: ValidationSeverity
    category: str
    message: str
    message_name: str = ""
    signal_name: str = ""
    suggestion: str = ""

    def __str__(self) -> str:
        prefix = f"[{self.severity.value.upper()}]"
        location = f"({self.message_name}" + (f"::{self.signal_name}" if self.signal_name else "") + ")"
        result = f"{prefix} {location} {self.message}"
        if self.suggestion:
            result += f" -> Suggestion: {self.suggestion}"
        return result


@dataclass
class ValidationResult:
    """Aggregated validation result for a DBC file."""
    filename: str
    issues: list[ValidationIssue] = field(default_factory=list)
    auto_fixed: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def summary(self) -> str:
        lines = [
            f"DBC Validation: {self.filename}",
            f"  Errors: {self.error_count}",
            f"  Warnings: {self.warning_count}",
            f"  Auto-fixed: {len(self.auto_fixed)}",
        ]
        if self.issues:
            lines.append("  Details:")
            for issue in self.issues:
                lines.append(f"    {issue}")
        return "\n".join(lines)
