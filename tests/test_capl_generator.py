"""
Unit tests for CAPL Generator

Tests CAPL script generation for both signal simulation
and diagnostic testing scenarios.
"""

import pytest
from pathlib import Path

from src.dbc.parser import DBCParser
from src.signal.dependency_analyzer import SignalDependencyAnalyzer
from src.capl.generator import CAPLGenerator
from src.capl.oem_rules import OEMRulesEngine


EXAMPLE_DBC = str(Path(__file__).parent.parent / "examples" / "dbc" / "bcm_example.dbc")
BCM_SPEC = str(Path(__file__).parent.parent / "config" / "oem_specs" / "bcm_spec.yaml")


class TestCAPLGenerator:
    """Tests for CAPL script generation."""

    @pytest.fixture
    def dbc_model(self):
        parser = DBCParser()
        return parser.parse(EXAMPLE_DBC)

    @pytest.fixture
    def dep_graph(self, dbc_model):
        analyzer = SignalDependencyAnalyzer()
        return analyzer.analyze(dbc_model)

    def test_generate_signal_simulation(self, dbc_model, dep_graph):
        """Test signal simulation script generation."""
        generator = CAPLGenerator(spec_name="generic")
        script = generator.generate_signal_simulation(dbc_model, dep_graph)

        assert len(script) > 0
        assert "variables" in script or "//" in script
        assert "BCM_Status" in script

    def test_generate_diagnostic_test(self, dbc_model):
        """Test diagnostic test script generation."""
        generator = CAPLGenerator(spec_name="bcm_simplified")
        script = generator.generate_diagnostic_test(
            dbc_model, services=[0x22, 0x27, 0x19]
        )

        assert len(script) > 0
        assert "0x22" in script or "ReadDataByIdentifier" in script

    def test_generate_with_bcm_spec(self, dbc_model):
        """Test generation using BCM OEM specification."""
        generator = CAPLGenerator(spec=BCM_SPEC)
        script = generator.generate_signal_simulation(dbc_model)

        assert len(script) > 0

    def test_generate_for_specific_node(self, dbc_model, dep_graph):
        """Test generating scripts only for a specific sender node."""
        generator = CAPLGenerator(spec_name="generic")
        script = generator.generate_signal_simulation(
            dbc_model, dep_graph, target_node="BCM"
        )

        # Should contain BCM messages but not Engine messages
        assert "BCM_Status" in script

    def test_generate_diagnostic_with_security(self, dbc_model):
        """Test diagnostic test with security access."""
        generator = CAPLGenerator(spec_name="bcm_simplified")
        script = generator.generate_diagnostic_test(
            dbc_model, services=[0x2E, 0x31], security_seed=0xA5B6
        )

        assert "0xA5B6" in script or "SecurityAccess" in script


class TestOEMRulesEngine:
    """Tests for OEM specification rules engine."""

    def test_load_builtin_generic(self):
        """Test loading the built-in generic spec."""
        engine = OEMRulesEngine(spec_name="generic")
        assert engine.spec.oem_name == "Generic"

    def test_load_builtin_bcm(self):
        """Test loading the built-in BCM spec."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")
        assert engine.spec.oem_name == "BCM_Simplified"
        assert len(engine.spec.services) > 0

    def test_load_yaml_spec(self):
        """Test loading a YAML OEM specification file."""
        engine = OEMRulesEngine(spec_path=BCM_SPEC)
        assert engine.spec.oem_name == "BCM_Simplified"

    def test_service_rules(self):
        """Test service rule retrieval."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")

        rule_22 = engine.get_service_rule(0x22)
        assert rule_22 is not None
        assert rule_22.service_name == "ReadDataByIdentifier"
        assert not rule_22.sub_function_required

    def test_security_check(self):
        """Test security requirement checking."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")

        # 0x22 (ReadDataByIdentifier) doesn't require security
        assert not engine.requires_security(0x22)

        # 0x2E (WriteDataByIdentifier) requires security
        assert engine.requires_security(0x2E)

    def test_session_check(self):
        """Test session requirement checking."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")

        # 0x22 works in default session
        assert not engine.requires_extended_session(0x22)

        # 0x2E requires extended session
        assert engine.requires_extended_session(0x2E)

    def test_naming_convention(self):
        """Test OEM naming convention application."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")

        assert engine.format_message_name("Status") == "BCM_Status"
        assert engine.format_signal_name("DoorLock") == "Bcm_DoorLock"

        # Already prefixed should not double-prefix
        assert engine.format_message_name("BCM_Status") == "BCM_Status"

    def test_timeout(self):
        """Test service timeout retrieval."""
        engine = OEMRulesEngine(spec_name="bcm_simplified")

        timeout_22 = engine.get_timeout(0x22)
        assert timeout_22 == 2000

        # Unknown service should return default
        timeout_unknown = engine.get_timeout(0xFF)
        assert timeout_unknown == engine.spec.test_rules.max_wait_time_ms
