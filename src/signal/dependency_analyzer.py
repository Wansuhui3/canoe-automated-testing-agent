"""
Signal Dependency Analyzer

Analyzes signal dependencies within and across CAN messages,
including multiplexer-to-mux-signal mappings and cross-message
signal relationships.
"""

from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

from ..dbc.models import DBCModel, MessageDefinition, SignalDefinition, SignalType


@dataclass
class SignalNode:
    """Node in the signal dependency graph."""
    message_name: str
    signal_name: str
    message_id: int
    signal_type: SignalType
    mux_value: Optional[int] = None

    @property
    def full_name(self) -> str:
        return f"{self.message_name}.{self.signal_name}"

    def __hash__(self) -> int:
        return hash((self.message_name, self.signal_name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SignalNode):
            return False
        return self.message_name == other.message_name and self.signal_name == other.signal_name


@dataclass
class DependencyEdge:
    """Edge in the signal dependency graph."""
    source: SignalNode
    target: SignalNode
    dependency_type: str  # "multiplexer", "calculation", "condition"
    description: str = ""


@dataclass
class DependencyGraph:
    """
    Signal dependency graph built from DBC model analysis.

    Uses NetworkX directed graph for traversal and analysis.
    """
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    nodes: dict[str, SignalNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)

    def add_node(self, node: SignalNode) -> None:
        self.nodes[node.full_name] = node
        self.graph.add_node(node.full_name,
                            message_name=node.message_name,
                            signal_name=node.signal_name,
                            message_id=node.message_id,
                            signal_type=node.signal_type.value)

    def add_edge(self, edge: DependencyEdge) -> None:
        self.edges.append(edge)
        self.graph.add_edge(edge.source.full_name, edge.target.full_name,
                            dependency_type=edge.dependency_type,
                            description=edge.description)

    def get_dependencies(self, signal_full_name: str) -> list[SignalNode]:
        """Get all signals that this signal depends on."""
        if signal_full_name not in self.graph:
            return []
        predecessors = self.graph.predecessors(signal_full_name)
        return [self.nodes[name] for name in predecessors if name in self.nodes]

    def get_dependents(self, signal_full_name: str) -> list[SignalNode]:
        """Get all signals that depend on this signal."""
        if signal_full_name not in self.graph:
            return []
        successors = self.graph.successors(signal_full_name)
        return [self.nodes[name] for name in successors if name in self.nodes]

    def get_multiplexer_groups(self) -> dict[str, list[SignalNode]]:
        """Get all multiplexer groups: {mux_signal_name: [muxed_signals]}."""
        groups: dict[str, list[SignalNode]] = {}
        for edge in self.edges:
            if edge.dependency_type == "multiplexer":
                mux_name = edge.source.full_name
                if mux_name not in groups:
                    groups[mux_name] = []
                groups[mux_name].append(edge.target)
        return groups

    def topological_order(self) -> list[str]:
        """Return signals in topological order (dependencies first)."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # Graph has cycles, fall back to arbitrary order
            return list(self.graph.nodes)


class SignalDependencyAnalyzer:
    """
    Analyzes signal dependencies in a DBC model.

    Builds a directed graph where edges represent dependencies:
    - Multiplexer signals -> Multiplexed signals
    - Cross-message signal references (when calculators exist)
    """

    def __init__(self) -> None:
        self._graph = DependencyGraph()

    def analyze(self, dbc_model: DBCModel) -> DependencyGraph:
        """
        Analyze signal dependencies in the DBC model.

        Args:
            dbc_model: Parsed DBC model

        Returns:
            DependencyGraph with all signal nodes and dependency edges
        """
        self._graph = DependencyGraph()

        # Phase 1: Add all signal nodes
        for msg in dbc_model.messages:
            for sig in msg.signals:
                node = SignalNode(
                    message_name=msg.name,
                    signal_name=sig.name,
                    message_id=msg.id,
                    signal_type=sig.signal_type,
                    mux_value=sig.mux_value,
                )
                self._graph.add_node(node)

        # Phase 2: Add multiplexer dependency edges
        for msg in dbc_model.messages:
            mux_signal = msg.get_multiplexer_signal()
            if mux_signal:
                mux_node = self._graph.nodes.get(f"{msg.name}.{mux_signal.name}")
                for sig in msg.signals:
                    if sig.signal_type == SignalType.MULTIPLEXED:
                        muxed_node = self._graph.nodes.get(f"{msg.name}.{sig.name}")
                        if mux_node and muxed_node:
                            self._graph.add_edge(DependencyEdge(
                                source=mux_node,
                                target=muxed_node,
                                dependency_type="multiplexer",
                                description=f"Mux value {sig.mux_value}: "
                                            f"{mux_signal.name}={sig.mux_value} -> {sig.name}",
                            ))

        # Phase 3: Detect cross-message dependencies
        # (signals with same name across messages may indicate dependencies)
        self._detect_cross_message_deps(dbc_model)

        return self._graph

    def _detect_cross_message_deps(self, dbc_model: DBCModel) -> None:
        """Detect potential cross-message signal dependencies."""
        # Build signal name index
        signal_index: dict[str, list[SignalNode]] = {}
        for msg in dbc_model.messages:
            for sig in msg.signals:
                full_name = f"{msg.name}.{sig.name}"
                node = self._graph.nodes.get(full_name)
                if node:
                    base_name = sig.name.lower()
                    # Check for common dependency patterns
                    # e.g., "TrackValid" depends on "TrackID" existing
                    if base_name.endswith("valid") or base_name.endswith("status"):
                        base_signal = base_name.replace("valid", "").replace("status", "")
                        for other_msg in dbc_model.messages:
                            if other_msg.name == msg.name:
                                continue
                            for other_sig in other_msg.signals:
                                if other_sig.name.lower() == base_signal:
                                    other_full = f"{other_msg.name}.{other_sig.name}"
                                    other_node = self._graph.nodes.get(other_full)
                                    if other_node and node:
                                        self._graph.add_edge(DependencyEdge(
                                            source=other_node,
                                            target=node,
                                            dependency_type="condition",
                                            description=f"Signal {sig.name} validates "
                                                        f"{other_sig.name}",
                                        ))
