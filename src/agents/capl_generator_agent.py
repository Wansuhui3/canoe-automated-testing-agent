"""
CAPL Generator Sub-Agent

Generates CAPL test scripts based on DBC models, signal dependencies,
and OEM specifications. Supports both signal simulation and
diagnostic testing scenarios.
"""

import logging
from pathlib import Path
from typing import Optional

from ..dbc.models import DBCModel
from ..signal.dependency_analyzer import DependencyGraph
from ..capl.generator import CAPLGenerator
from ..capl.oem_rules import OEMRulesEngine

logger = logging.getLogger(__name__)


class CAPLGeneratorAgent:
    """
    CAPL Generator Sub-Agent: Third stage in the testing pipeline.

    Responsibilities:
    1. Generate OEM-compliant signal simulation CAPL scripts
    2. Generate UDS diagnostic test CAPL scripts
    3. Apply OEM naming conventions and service rules
    4. Handle multiplexer switching in generated scripts
    5. Output ready-to-use CAPL files for CANoe

    Pipeline Flow:
        DBCModel + DependencyGraph -> CAPLGeneratorAgent -> CAPL Scripts -> VerificationAgent
    """

    def __init__(self, spec: Optional[str] = None, spec_name: str = "generic") -> None:
        """
        Initialize the CAPL Generator Agent.

        Args:
            spec: Path to OEM specification YAML file
            spec_name: Built-in OEM spec name (e.g., "bcm_simplified")
        """
        self.generator = CAPLGenerator(spec=spec, spec_name=spec_name)
        self.oem_engine = OEMRulesEngine(spec_path=spec, spec_name=spec_name)
        self._last_signal_script: Optional[str] = None
        self._last_diag_script: Optional[str] = None

    def generate_signal_simulation(
        self,
        dbc_model: DBCModel,
        dep_graph: Optional[DependencyGraph] = None,
        target_node: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a CAPL signal simulation script.

        Args:
            dbc_model: Parsed DBC model
            dep_graph: Signal dependency graph (for mux-aware generation)
            target_node: Only generate for this sender node
            output_path: Path to write the .capl file

        Returns:
            Generated CAPL script content
        """
        logger.info(
            f"[CAPL Generator Agent] Generating signal simulation: "
            f"{dbc_model.filename}, target={target_node or 'all'}"
        )

        self._last_signal_script = self.generator.generate_signal_simulation(
            dbc_model=dbc_model,
            dep_graph=dep_graph,
            target_node=target_node,
        )

        # Count generated lines and functions
        line_count = len(self._last_signal_script.splitlines())
        logger.info(f"[CAPL Generator Agent] Signal script generated: {line_count} lines")

        if output_path:
            self._write_script(self._last_signal_script, output_path)

        return self._last_signal_script

    def generate_diagnostic_test(
        self,
        dbc_model: DBCModel,
        services: Optional[list[int]] = None,
        security_seed: int = 0xA5B6,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a CAPL UDS diagnostic test script.

        Args:
            dbc_model: Parsed DBC model
            services: List of UDS service IDs to test (None = all known)
            security_seed: Security seed for simplified testing
            output_path: Path to write the .capl file

        Returns:
            Generated CAPL script content
        """
        logger.info(
            f"[CAPL Generator Agent] Generating diagnostic test: "
            f"{dbc_model.filename}, services={services or 'all'}"
        )

        self._last_diag_script = self.generator.generate_diagnostic_test(
            dbc_model=dbc_model,
            services=services,
            security_seed=security_seed,
        )

        line_count = len(self._last_diag_script.splitlines())
        logger.info(f"[CAPL Generator Agent] Diagnostic script generated: {line_count} lines")

        if output_path:
            self._write_script(self._last_diag_script, output_path)

        return self._last_diag_script

    def generate_all(
        self,
        dbc_model: DBCModel,
        dep_graph: Optional[DependencyGraph] = None,
        output_dir: Optional[str] = None,
        services: Optional[list[int]] = None,
        security_seed: int = 0xA5B6,
    ) -> dict[str, str]:
        """
        Generate all CAPL scripts (signal + diagnostic).

        Args:
            dbc_model: Parsed DBC model
            dep_graph: Signal dependency graph
            output_dir: Directory to write output files
            services: UDS service IDs for diagnostic test
            security_seed: Security seed

        Returns:
            Dictionary: {"signal_sim": content, "diag_test": content}
        """
        results = {}

        signal_path = f"{output_dir}/{dbc_model.filename}_signal_sim.capl" if output_dir else None
        results["signal_sim"] = self.generate_signal_simulation(
            dbc_model, dep_graph, output_path=signal_path
        )

        diag_path = f"{output_dir}/{dbc_model.filename}_diag_test.capl" if output_dir else None
        results["diag_test"] = self.generate_diagnostic_test(
            dbc_model, services, security_seed, output_path=diag_path
        )

        return results

    @staticmethod
    def _write_script(content: str, path: str) -> None:
        """Write a CAPL script to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[CAPL Generator Agent] Script written: {path}")
