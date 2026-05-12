"""
Signal Reasoner Sub-Agent

Analyzes signal dependencies using long-chain reasoning,
identifies multiplexer mappings, and builds dependency graphs
for downstream CAPL generation.
"""

import logging
from typing import Optional

from ..dbc.models import DBCModel
from ..signal.dependency_analyzer import SignalDependencyAnalyzer, DependencyGraph
from ..signal.mux_handler import MultiplexHandler

logger = logging.getLogger(__name__)


class SignalReasonerAgent:
    """
    Signal Reasoner Sub-Agent: Second stage in the testing pipeline.

    Responsibilities:
    1. Build signal dependency graph from DBC model
    2. Analyze multiplexer-to-mux-signal mappings
    3. Identify cross-message signal relationships
    4. Determine signal send/receive ordering
    5. Provide dependency-aware data for CAPL generation

    Pipeline Flow:
        DBCModel -> SignalReasonerAgent -> DependencyGraph -> CAPLGeneratorAgent

    The "long-chain reasoning" aspect refers to the multi-step analysis:
    - Step 1: Identify all multiplexer signals and their mux values
    - Step 2: Map mux values to their controlled signal groups
    - Step 3: Detect cross-message dependencies (e.g., validation signals)
    - Step 4: Compute topological ordering for test execution
    - Step 5: Generate mux switching sequences for full coverage
    """

    def __init__(self) -> None:
        self.dependency_analyzer = SignalDependencyAnalyzer()
        self.mux_handler = MultiplexHandler()
        self._last_graph: Optional[DependencyGraph] = None

    def analyze(self, dbc_model: DBCModel) -> DependencyGraph:
        """
        Perform full dependency analysis on a DBC model.

        Args:
            dbc_model: Parsed DBC model from DBCParseAgent

        Returns:
            DependencyGraph with all signal nodes and dependency edges
        """
        logger.info(f"[Signal Reasoner Agent] Analyzing: {dbc_model.filename}")

        # Step 1-3: Build dependency graph
        self._last_graph = self.dependency_analyzer.analyze(dbc_model)
        logger.info(
            f"[Signal Reasoner Agent] Built graph: "
            f"{self._last_graph.graph.number_of_nodes()} nodes, "
            f"{self._last_graph.graph.number_of_edges()} edges"
        )

        # Step 4: Analyze multiplexer groups
        for msg in dbc_model.messages:
            mux_signal = msg.get_multiplexer_signal()
            if mux_signal:
                mux_groups = self.mux_handler.analyze_message(msg)
                coverage = self.mux_handler.get_coverage_report(msg)
                logger.info(
                    f"[Signal Reasoner Agent] Message '{msg.name}': "
                    f"mux signal '{mux_signal.name}', "
                    f"{len(mux_groups)} mux groups, "
                    f"coverage={coverage.get('coverage_ratio', 0):.1%}"
                )

                # Check for mux consistency issues
                warnings = self.mux_handler.check_mux_consistency(msg)
                for w in warnings:
                    logger.warning(f"[Signal Reasoner Agent] Mux warning: {w}")

        # Step 5: Compute topological order for test execution
        topo_order = self._last_graph.topological_order()
        logger.info(f"[Signal Reasoner Agent] Topological order computed ({len(topo_order)} signals)")

        return self._last_graph

    def get_mux_switch_sequences(self, dbc_model: DBCModel) -> dict[str, list[int]]:
        """
        Get mux switch sequences for all messages with multiplexing.

        Args:
            dbc_model: Parsed DBC model

        Returns:
            Dictionary: {message_name: [mux_value_sequence]}
        """
        sequences = {}
        for msg in dbc_model.messages:
            seq = self.mux_handler.generate_switch_sequence(msg)
            if seq:
                sequences[msg.name] = seq.mux_values
                logger.info(
                    f"[Signal Reasoner Agent] Mux sequence for '{msg.name}': {seq.mux_values}"
                )
        return sequences

    def get_dependency_order(self) -> list[str]:
        """
        Get signals in dependency order (safe execution sequence).

        Returns:
            List of signal full names in topological order
        """
        if self._last_graph:
            return self._last_graph.topological_order()
        return []

    @property
    def last_graph(self) -> Optional[DependencyGraph]:
        """Get the last computed dependency graph."""
        return self._last_graph
