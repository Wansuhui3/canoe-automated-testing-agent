"""
DBC Parser Sub-Agent

Orchestrates DBC file parsing and validation, providing a high-level
interface for the multi-agent pipeline.
"""

import logging
from pathlib import Path
from typing import Optional

from ..dbc.parser import DBCParser
from ..dbc.validator import DBCValidator
from ..dbc.models import DBCModel, ValidationResult

logger = logging.getLogger(__name__)


class DBCParseAgent:
    """
    DBC Parser Sub-Agent: First stage in the testing pipeline.

    Responsibilities:
    1. Parse DBC files into structured models
    2. Validate signal definitions (bit positions, byte order, multiplexing)
    3. Identify and optionally fix non-compliant definitions
    4. Output validated DBC model for downstream agents

    Pipeline Flow:
        DBC File -> DBCParseAgent -> Validated DBCModel -> SignalReasonerAgent
    """

    def __init__(self, auto_fix: bool = False) -> None:
        """
        Initialize the DBC Parser Agent.

        Args:
            auto_fix: If True, automatically fix fixable issues
        """
        self.parser = DBCParser()
        self.validator = DBCValidator(auto_fix=auto_fix)
        self.auto_fix = auto_fix
        self._last_model: Optional[DBCModel] = None
        self._last_validation: Optional[ValidationResult] = None

    def parse(self, dbc_path: str) -> DBCModel:
        """
        Parse a DBC file into a structured model.

        Args:
            dbc_path: Path to the .dbc file

        Returns:
            Parsed DBCModel

        Raises:
            FileNotFoundError: If DBC file doesn't exist
        """
        if not Path(dbc_path).exists():
            raise FileNotFoundError(f"DBC file not found: {dbc_path}")

        logger.info(f"[DBC Parse Agent] Parsing: {dbc_path}")
        self._last_model = self.parser.parse(dbc_path)
        logger.info(
            f"[DBC Parse Agent] Parsed {len(self._last_model.messages)} messages, "
            f"{len(self._last_model.nodes)} nodes"
        )
        return self._last_model

    def validate(self, dbc_model: Optional[DBCModel] = None) -> ValidationResult:
        """
        Validate a DBC model for issues.

        Args:
            dbc_model: DBC model to validate (uses last parsed if None)

        Returns:
            ValidationResult with all found issues
        """
        model = dbc_model or self._last_model
        if model is None:
            raise ValueError("No DBC model available. Call parse() first.")

        logger.info(f"[DBC Parse Agent] Validating: {model.filename}")
        self._last_validation = self.validator.validate(model)

        logger.info(
            f"[DBC Parse Agent] Validation complete: "
            f"{self._last_validation.error_count} errors, "
            f"{self._last_validation.warning_count} warnings"
        )

        if self._last_validation.has_errors:
            logger.warning(self._last_validation.summary())

        return self._last_validation

    def parse_and_validate(self, dbc_path: str) -> tuple[DBCModel, ValidationResult]:
        """
        Convenience method: parse and validate in one call.

        Args:
            dbc_path: Path to the .dbc file

        Returns:
            Tuple of (DBCModel, ValidationResult)
        """
        model = self.parse(dbc_path)
        validation = self.validate(model)
        return model, validation

    @property
    def last_model(self) -> Optional[DBCModel]:
        """Get the last parsed DBC model."""
        return self._last_model

    @property
    def last_validation(self) -> Optional[ValidationResult]:
        """Get the last validation result."""
        return self._last_validation

    def get_summary(self) -> str:
        """Get a summary of the last parse and validation results."""
        if not self._last_model:
            return "No DBC file parsed yet."

        lines = [
            f"DBC: {self._last_model.filename}",
            f"  Messages: {len(self._last_model.messages)}",
            f"  Nodes: {len(self._last_model.nodes)}",
        ]

        total_signals = sum(len(m.signals) for m in self._last_model.messages)
        lines.append(f"  Total signals: {total_signals}")

        if self._last_validation:
            lines.extend([
                f"  Validation errors: {self._last_validation.error_count}",
                f"  Validation warnings: {self._last_validation.warning_count}",
            ])

        return "\n".join(lines)
