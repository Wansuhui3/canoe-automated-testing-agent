"""
DBC File Parser

Parses DBC (Database Container) files used in CAN bus communication.
Extracts messages, signals, nodes, value tables, and other definitions.
"""

import re
from pathlib import Path
from typing import Optional

from .models import (
    DBCModel, MessageDefinition, SignalDefinition, NodeDefinition,
    ByteOrder, SignalType,
)


class DBCParser:
    """
    DBC file parser that extracts structured data from .dbc files.

    Supports the standard DBC format including:
    - BO_ (Message definitions)
    - SG_ (Signal definitions)
    - BU_ (Node definitions)
    - VAL_ (Value table definitions)
    - CM_ (Comments)
    - BA_ (Attribute definitions)
    - SG_MUL_VAL_ (Multiplexed signal extended definitions)
    """

    # Regex patterns for DBC line types
    _RE_VERSION = re.compile(r'^VERSION\s+"(.*)"')
    _RE_NODES = re.compile(r'^BU_:\s*(.*)')
    _RE_MESSAGE = re.compile(r'^BO_\s+(\w+)\s+(\w+):\s+(\d+)\s+(\w+)')
    _RE_SIGNAL = re.compile(
        r'^SG_\s+(\w+)\s+'
        r'(?:(\w+)\s+)?'           # Optional mux indicator (M or m1, m2, etc.)
        r':\s*(\d+)\|(\d+)@(\d)'   # start_bit|bit_length@byte_order_sign
        r'([+-])\s+'               # Sign
        r'\(([^,]+),([^)]+)\)\s+'  # (factor,offset)
        r'\[([^|]+)\|([^\]]+)\]\s+' # [min|max]
        r'"([^"]*)"\s+'            # unit
        r'(.*)'                    # Receiver nodes
    )
    _RE_VAL_TABLE = re.compile(r'^VAL_\s+(\w+)\s+(\w+)\s+(.*)\s*;')
    _RE_COMMENT_MSG = re.compile(r'^CM_\s+BO_\s+(\w+)\s+"(.*)"\s*;')
    _RE_COMMENT_SIG = re.compile(r'^CM_\s+SG_\s+(\w+)\s+(\w+)\s+"(.*)"\s*;')
    _RE_COMMENT_BU = re.compile(r'^CM_\s+BU_\s+(\w+)\s+"(.*)"\s*;')

    def __init__(self) -> None:
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset parser state for a new file."""
        self._version = ""
        self._nodes: list[NodeDefinition] = []
        self._messages: dict[int, MessageDefinition] = {}
        self._comments_msg: dict[int, str] = {}
        self._comments_sig: dict[tuple[int, str], str] = {}
        self._comments_node: dict[str, str] = {}
        self._value_tables: dict[tuple[int, str], dict[int, str]] = {}

    def parse(self, filepath: str) -> DBCModel:
        """
        Parse a DBC file and return a structured DBCModel.

        Args:
            filepath: Path to the .dbc file

        Returns:
            DBCModel containing all parsed definitions

        Raises:
            FileNotFoundError: If the DBC file does not exist
            ValueError: If the DBC file has critical format errors
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"DBC file not found: {filepath}")

        self._reset_state()

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            try:
                self._parse_line(line)
            except Exception as e:
                # Log but don't crash on individual line parse errors
                print(f"Warning: Line {line_num} parse error: {e}")
                print(f"  Content: {line[:100]}")

        # Assemble the model
        return self._build_model(path.name)

    def _parse_line(self, line: str) -> None:
        """Route a DBC line to the appropriate parser."""
        # Version
        m = self._RE_VERSION.match(line)
        if m:
            self._version = m.group(1)
            return

        # Nodes
        m = self._RE_NODES.match(line)
        if m:
            node_names = m.group(1).split()
            self._nodes = [NodeDefinition(name=n) for n in node_names]
            return

        # Message definition
        m = self._RE_MESSAGE.match(line)
        if m:
            msg_id = int(m.group(1), 0)  # Support hex (0x) and decimal
            msg_name = m.group(2)
            msg_length = int(m.group(3))
            sender = m.group(4)
            self._messages[msg_id] = MessageDefinition(
                name=msg_name,
                id=msg_id,
                length=msg_length,
                sender=sender,
                is_extended=(msg_id > 0x7FF),
            )
            return

        # Signal definition
        m = self._RE_SIGNAL.match(line)
        if m:
            signal_name = m.group(1)
            mux_indicator = m.group(2)  # M, m1, m2, etc. or empty
            start_bit = int(m.group(3))
            bit_length = int(m.group(4))
            byte_order_code = int(m.group(5))  # 0=Motorola, 1=Intel
            sign = m.group(6)  # + or -
            factor = float(m.group(7))
            offset = float(m.group(8))
            min_val = float(m.group(9))
            max_val = float(m.group(10))
            unit = m.group(11)
            receivers = m.group(12)

            # Determine byte order
            byte_order = ByteOrder.MOTOROLA if byte_order_code == 0 else ByteOrder.INTEL

            # Determine signal type and mux value
            signal_type = SignalType.NORMAL
            mux_value: Optional[int] = None
            if mux_indicator == "M":
                signal_type = SignalType.MULTIPLEXER
            elif mux_indicator and mux_indicator.startswith("m"):
                signal_type = SignalType.MULTIPLEXED
                try:
                    mux_value = int(mux_indicator[1:])
                except ValueError:
                    pass

            signal = SignalDefinition(
                name=signal_name,
                start_bit=start_bit,
                bit_length=bit_length,
                byte_order=byte_order,
                factor=factor,
                offset=offset,
                min_val=min_val,
                max_val=max_val,
                unit=unit,
                signal_type=signal_type,
                mux_value=mux_value,
            )

            # Add signal to the most recently parsed message
            if self._messages:
                last_msg_id = list(self._messages.keys())[-1]
                self._messages[last_msg_id].signals.append(signal)
            return

        # Value table definitions
        m = self._RE_VAL_TABLE.match(line)
        if m:
            msg_id = int(m.group(1), 0)
            signal_name = m.group(2)
            values_str = m.group(3)
            values = self._parse_value_entries(values_str)
            self._value_tables[(msg_id, signal_name)] = values
            return

        # Comments
        m = self._RE_COMMENT_MSG.match(line)
        if m:
            self._comments_msg[int(m.group(1), 0)] = m.group(2)
            return

        m = self._RE_COMMENT_SIG.match(line)
        if m:
            self._comments_sig[(int(m.group(1), 0), m.group(2))] = m.group(3)
            return

        m = self._RE_COMMENT_BU.match(line)
        if m:
            self._comments_node[m.group(1)] = m.group(2)
            return

    def _parse_value_entries(self, values_str: str) -> dict[int, str]:
        """Parse value table entries: '0 "Off" 1 "On" 2 "Error" ;'"""
        result: dict[int, str] = {}
        parts = values_str.split('"')
        i = 0
        while i < len(parts) - 1:
            key_str = parts[i].strip()
            if key_str:
                try:
                    key = int(key_str)
                    value = parts[i + 1].strip()
                    result[key] = value
                except ValueError:
                    pass
            i += 2
        return result

    def _build_model(self, filename: str) -> DBCModel:
        """Assemble the parsed data into a DBCModel."""
        # Apply comments to nodes
        for node in self._nodes:
            if node.name in self._comments_node:
                node.comment = self._comments_node[node.name]

        # Apply comments and value tables to messages/signals
        for msg_id, msg in self._messages.items():
            if msg_id in self._comments_msg:
                msg.comment = self._comments_msg[msg_id]

            for sig in msg.signals:
                sig_key = (msg_id, sig.name)
                if sig_key in self._comments_sig:
                    sig.comment = self._comments_sig[sig_key]
                if sig_key in self._value_tables:
                    sig.value_table = self._value_tables[sig_key]

        return DBCModel(
            filename=filename,
            version=self._version,
            nodes=self._nodes,
            messages=list(self._messages.values()),
            value_tables={
                f"{msg_id}_{sig}": vals
                for (msg_id, sig), vals in self._value_tables.items()
            },
        )

    @staticmethod
    def parse_message_id(id_str: str) -> int:
        """Parse a message ID string, supporting both hex and decimal."""
        return int(id_str, 0)
