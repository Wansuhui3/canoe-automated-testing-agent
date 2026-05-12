"""
Unit tests for Signal Reasoner

Tests signal dependency analysis, multiplexer handling,
and dependency graph construction.
"""

import pytest
from pathlib import Path

from src.dbc.parser import DBCParser
from src.signal.dependency_analyzer import SignalDependencyAnalyzer, SignalNode
from src.signal.mux_handler import MultiplexHandler


EXAMPLE_DBC = str(Path(__file__).parent.parent / "examples" / "dbc" / "bcm_example.dbc")


class TestSignalDependencyAnalyzer:
    """Tests for signal dependency analysis."""

    @pytest.fixture
    def dbc_model(self):
        parser = DBCParser()
        return parser.parse(EXAMPLE_DBC)

    def test_analyze_builds_graph(self, dbc_model):
        """Test that analysis produces a dependency graph."""
        analyzer = SignalDependencyAnalyzer()
        graph = analyzer.analyze(dbc_model)

        assert graph.graph.number_of_nodes() > 0
        assert len(graph.nodes) > 0

    def test_multiplexer_edges(self, dbc_model):
        """Test that multiplexer-to-muxed-signal edges are created."""
        analyzer = SignalDependencyAnalyzer()
        graph = analyzer.analyze(dbc_model)

        mux_groups = graph.get_multiplexer_groups()
        # BCM_Status has BCM_Odometer as multiplexer
        assert len(mux_groups) > 0

    def test_topological_order(self, dbc_model):
        """Test that topological order is computed."""
        analyzer = SignalDependencyAnalyzer()
        graph = analyzer.analyze(dbc_model)

        order = graph.topological_order()
        assert len(order) > 0
        assert len(order) == graph.graph.number_of_nodes()

    def test_signal_node_properties(self):
        """Test SignalNode properties."""
        node = SignalNode(
            message_name="TestMsg",
            signal_name="TestSig",
            message_id=0x100,
            signal_type="normal",
        )
        assert node.full_name == "TestMsg.TestSig"
        assert hash(node) == hash(("TestMsg", "TestSig"))


class TestMultiplexHandler:
    """Tests for multiplexer handling."""

    @pytest.fixture
    def dbc_model(self):
        parser = DBCParser()
        return parser.parse(EXAMPLE_DBC)

    def test_analyze_message(self, dbc_model):
        """Test multiplexer group extraction."""
        handler = MultiplexHandler()
        bcm_msg = dbc_model.get_message("BCM_Status")

        if bcm_msg:
            groups = handler.analyze_message(bcm_msg)
            # BCM_Odometer is the mux signal
            assert len(groups) > 0

    def test_generate_switch_sequence(self, dbc_model):
        """Test mux switch sequence generation."""
        handler = MultiplexHandler()
        bcm_msg = dbc_model.get_message("BCM_Status")

        if bcm_msg:
            seq = handler.generate_switch_sequence(bcm_msg)
            if seq:
                assert len(seq) > 0
                assert seq.mux_signal_name == "BCM_Odometer"

    def test_coverage_report(self, dbc_model):
        """Test mux coverage report generation."""
        handler = MultiplexHandler()
        bcm_msg = dbc_model.get_message("BCM_Status")

        if bcm_msg:
            report = handler.get_coverage_report(bcm_msg)
            if report["has_multiplexing"]:
                assert "coverage_ratio" in report
                assert 0 <= report["coverage_ratio"] <= 1

    def test_no_multiplexing(self, dbc_model):
        """Test handling messages without multiplexing."""
        handler = MultiplexHandler()
        engine_msg = dbc_model.get_message("EngineData")

        if engine_msg:
            seq = handler.generate_switch_sequence(engine_msg)
            assert seq is None  # No mux in EngineData

    def test_mux_consistency(self, dbc_model):
        """Test mux consistency checking."""
        handler = MultiplexHandler()
        for msg in dbc_model.messages:
            warnings = handler.check_mux_consistency(msg)
            # Just ensure it doesn't crash
            assert isinstance(warnings, list)
