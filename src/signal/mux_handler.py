"""
Multiplexer Signal Handler

Manages multiplexed signal groups, validates mux value consistency,
and generates mux switching sequences for test scenarios.
"""

from dataclasses import dataclass
from typing import Optional

from ..dbc.models import (
    MessageDefinition, SignalDefinition, SignalType,
)


@dataclass
class MuxGroup:
    """A group of signals sharing the same multiplexer value."""
    mux_value: int
    signals: list[SignalDefinition]
    message_name: str

    @property
    def signal_names(self) -> list[str]:
        return [s.name for s in self.signals]

    @property
    def total_bits(self) -> int:
        """Total bits occupied by all signals in this group."""
        return sum(s.bit_length for s in self.signals)


@dataclass
class MuxSwitchSequence:
    """
    Sequence of multiplexer switch operations for test coverage.

    Defines the order and values to set the multiplexer signal
    to ensure all mux groups are tested.
    """
    message_name: str
    mux_signal_name: str
    mux_values: list[int]
    descriptions: dict[int, str]

    def __len__(self) -> int:
        return len(self.mux_values)


class MultiplexHandler:
    """
    Handles multiplexed signal analysis and test sequence generation.

    Capabilities:
    - Extract and organize multiplexer groups
    - Validate mux value consistency
    - Generate mux switching sequences for test coverage
    - Check for mux value gaps or conflicts
    """

    def analyze_message(self, msg: MessageDefinition) -> list[MuxGroup]:
        """
        Analyze a message's multiplexing structure.

        Args:
            msg: Message definition to analyze

        Returns:
            List of MuxGroup objects, one per unique mux value
        """
        mux_groups_dict = msg.get_multiplexer_signals()
        result = []
        for mux_val, signals in sorted(mux_groups_dict.items()):
            result.append(MuxGroup(
                mux_value=mux_val,
                signals=signals,
                message_name=msg.name,
            ))
        return result

    def generate_switch_sequence(self, msg: MessageDefinition) -> Optional[MuxSwitchSequence]:
        """
        Generate a mux switch sequence that covers all mux groups.

        Args:
            msg: Message definition with multiplexer

        Returns:
            MuxSwitchSequence or None if message has no multiplexer
        """
        mux_signal = msg.get_multiplexer_signal()
        if not mux_signal:
            return None

        mux_groups = self.analyze_message(msg)
        mux_values = sorted(g.mux_value for g in mux_groups)

        descriptions = {}
        for group in mux_groups:
            signal_list = ", ".join(group.signal_names)
            descriptions[group.mux_value] = (
                f"Mux={group.mux_value}: {signal_list}"
            )

        return MuxSwitchSequence(
            message_name=msg.name,
            mux_signal_name=mux_signal.name,
            mux_values=mux_values,
            descriptions=descriptions,
        )

    def check_mux_consistency(self, msg: MessageDefinition) -> list[str]:
        """
        Check for mux value consistency issues.

        Returns:
            List of warning messages
        """
        warnings = []
        mux_signal = msg.get_multiplexer_signal()
        if not mux_signal:
            return warnings

        mux_groups = self.analyze_message(msg)

        # Check for gaps in mux values
        if len(mux_groups) >= 2:
            values = sorted(g.mux_value for g in mux_groups)
            for i in range(len(values) - 1):
                if values[i + 1] - values[i] > 1:
                    warnings.append(
                        f"Gap in mux values: {values[i]} -> {values[i+1]} "
                        f"(missing {values[i]+1} to {values[i+1]-1})"
                    )

        # Check for bit overlap within mux groups
        for group in mux_groups:
            occupied: dict[int, str] = {}
            for sig in group.signals:
                for bit in range(sig.start_bit, sig.start_bit + sig.bit_length):
                    if bit in occupied:
                        warnings.append(
                            f"Bit overlap in mux={group.mux_value}: "
                            f"bit {bit} used by both '{occupied[bit]}' and '{sig.name}'"
                        )
                    else:
                        occupied[bit] = sig.name

        # Check mux signal range covers all mux values
        max_mux_val = max(g.mux_value for g in mux_groups) if mux_groups else 0
        max_possible = (1 << mux_signal.bit_length) - 1
        if max_mux_val > max_possible:
            warnings.append(
                f"Mux value {max_mux_val} exceeds mux signal capacity "
                f"({mux_signal.bit_length} bits, max={max_possible})"
            )

        return warnings

    def get_coverage_report(self, msg: MessageDefinition) -> dict:
        """
        Generate a mux coverage report for a message.

        Returns:
            Dictionary with coverage statistics
        """
        mux_signal = msg.get_multiplexer_signal()
        if not mux_signal:
            return {"has_multiplexing": False}

        mux_groups = self.analyze_message(msg)
        max_possible = (1 << mux_signal.bit_length)

        return {
            "has_multiplexing": True,
            "mux_signal": mux_signal.name,
            "mux_bit_length": mux_signal.bit_length,
            "total_possible_values": max_possible,
            "defined_values": len(mux_groups),
            "coverage_ratio": len(mux_groups) / max_possible,
            "mux_values": [g.mux_value for g in mux_groups],
            "signals_per_group": {
                g.mux_value: len(g.signals) for g in mux_groups
            },
        }
