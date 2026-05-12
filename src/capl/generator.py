"""
CAPL Code Generator

Generates CAPL (Communication Access Programming Language) test scripts
based on DBC model, signal dependency graph, and OEM specifications.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from ..dbc.models import DBCModel, MessageDefinition, SignalDefinition, SignalType, ByteOrder
from ..signal.dependency_analyzer import DependencyGraph
from .oem_rules import OEMRulesEngine


class CAPLGenerator:
    """
    Generates CAPL test scripts from DBC models and OEM specifications.

    Supports generating:
    - Signal simulation scripts (send cyclic CAN messages)
    - Diagnostic test scripts (UDS service interactions)
    - Signal verification scripts (check expected vs. actual values)
    - Multiplexer test scripts (switch mux values and verify)
    """

    def __init__(self, spec: Optional[str] = None, spec_name: str = "generic") -> None:
        """
        Initialize the CAPL generator.

        Args:
            spec: Path to OEM specification YAML file
            spec_name: Built-in OEM spec name to use
        """
        self.oem_engine = OEMRulesEngine(spec_path=spec, spec_name=spec_name)
        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_signal_simulation(
        self,
        dbc_model: DBCModel,
        dep_graph: Optional[DependencyGraph] = None,
        target_node: Optional[str] = None,
    ) -> str:
        """
        Generate a CAPL script for signal simulation (sending messages).

        Args:
            dbc_model: Parsed DBC model
            dep_graph: Signal dependency graph (optional, for mux handling)
            target_node: Only generate for messages sent by this node

        Returns:
            Generated CAPL script content
        """
        messages = dbc_model.messages
        if target_node:
            messages = [m for m in messages if m.sender == target_node]

        # Prepare template context
        context = {
            "script_name": f"{dbc_model.filename}_signal_sim",
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dbc_filename": dbc_model.filename,
            "messages": messages,
            "oem_spec": self.oem_engine.spec,
            "dep_graph": dep_graph,
        }

        try:
            template = self._env.get_template("signal_test.capl")
            return template.render(**context)
        except Exception:
            # Fallback: generate without template
            return self._generate_signal_sim_fallback(messages)

    def generate_diagnostic_test(
        self,
        dbc_model: DBCModel,
        services: Optional[list[int]] = None,
        security_seed: int = 0xA5B6,
    ) -> str:
        """
        Generate a CAPL script for UDS diagnostic testing.

        Args:
            dbc_model: Parsed DBC model
            services: List of UDS service IDs to test (None = all known)
            security_seed: Fixed security seed for simplified testing
        Returns:
            Generated CAPL script content
        """
        if services is None:
            services = sorted(self.oem_engine.spec.services.keys())

        test_cases = self._build_diagnostic_test_cases(services)

        context = {
            "script_name": f"{dbc_model.filename}_diag_test",
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dbc_filename": dbc_model.filename,
            "test_cases": test_cases,
            "security_seed": security_seed,
            "oem_spec": self.oem_engine.spec,
        }

        try:
            template = self._env.get_template("diagnostic_test.capl")
            return template.render(**context)
        except Exception:
            return self._generate_diagnostic_test_fallback(test_cases, security_seed)

    def _build_diagnostic_test_cases(self, services: list[int]) -> list[dict]:
        """Build structured test case data for diagnostic services."""
        test_cases = []
        for sid in services:
            rule = self.oem_engine.get_service_rule(sid)
            test_cases.append({
                "service_id": sid,
                "service_name": rule.service_name if rule else f"Service_0x{sid:02X}",
                "sub_function_required": rule.sub_function_required if rule else False,
                "requires_security": self.oem_engine.requires_security(sid),
                "requires_extended_session": self.oem_engine.requires_extended_session(sid),
                "timeout_ms": self.oem_engine.get_timeout(sid),
            })
        return test_cases

    def _generate_signal_sim_fallback(self, messages: list[MessageDefinition]) -> str:
        """Fallback CAPL signal simulation generator (no template)."""
        lines = [
            "//===============================================================",
            f"// Auto-generated CAPL Signal Simulation Script",
            f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "//===============================================================",
            "",
            "variables {",
        ]

        # Declare message variables
        for msg in messages:
            lines.append(f"  message 0x{msg.id:X} {msg.name};")

        lines.extend([
            "}",
            "",
            "on start {",
        ])

        # Set signal initial values and start timers
        for msg in messages:
            for sig in msg.signals:
                if sig.signal_type != SignalType.MULTIPLEXER:
                    init_val = sig.physical_to_raw(0.0) if sig.offset == 0 else 0
                    lines.append(f"  ${msg.name}::{sig.name} = {init_val};")
            if msg.cycle_time > 0:
                lines.append(f"  setTimer(cycle_{msg.name}, {msg.cycle_time});")

        lines.extend([
            "}",
            "",
        ])

        # Timer handlers
        for msg in messages:
            if msg.cycle_time > 0:
                lines.extend([
                    f"on timer cycle_{msg.name} {{",
                    f"  output({msg.name});",
                    f"  setTimer(cycle_{msg.name}, {msg.cycle_time});",
                    f"}}",
                    "",
                ])

        return "\n".join(lines)

    def _generate_diagnostic_test_fallback(
        self, test_cases: list[dict], security_seed: int
    ) -> str:
        """Fallback CAPL diagnostic test generator (no template)."""
        lines = [
            "//===============================================================",
            f"// Auto-generated CAPL Diagnostic Test Script",
            f"// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "//===============================================================",
            "",
            "variables {",
            "  message 0x700 DiagRequest;",
            "  message 0x7E8 DiagResponse;",
            f"  const int SECURITY_SEED = 0x{security_seed:04X};",
            "}",
            "",
            "on start {",
            "  write(\"=== UDS Diagnostic Test Started ===\");",
            "  testWaitForTimeout(1000);  // Wait for ECU startup",
        ]

        for tc in test_cases:
            sid = tc["service_id"]
            name = tc["service_name"]
            lines.extend([
                f"  // Test: {name} (0x{sid:02X})",
            ])

            if tc["requires_extended_session"]:
                lines.extend([
                    f"  // Enter extended session first",
                    f"  DiagRequest.byte(0) = 0x02;  // PCI",
                    f"  DiagRequest.byte(1) = 0x10;  // SID: DiagnosticSessionControl",
                    f"  DiagRequest.byte(2) = 0x03;  // Sub: Extended Session",
                    f"  output(DiagRequest);",
                    f"  testWaitForTimeout({tc['timeout_ms']});",
                ])

            if tc["requires_security"]:
                lines.extend([
                    f"  // Security Access (Seed)",
                    f"  DiagRequest.byte(0) = 0x02;",
                    f"  DiagRequest.byte(1) = 0x27;  // SID: SecurityAccess",
                    f"  DiagRequest.byte(2) = 0x01;  // Sub: Request Seed",
                    f"  output(DiagRequest);",
                    f"  testWaitForTimeout({tc['timeout_ms']});",
                    f"  // Security Access (Key) - simplified: accept any key",
                    f"  DiagRequest.byte(0) = 0x04;",
                    f"  DiagRequest.byte(1) = 0x27;  // SID: SecurityAccess",
                    f"  DiagRequest.byte(2) = 0x02;  // Sub: Send Key",
                    f"  DiagRequest.byte(3) = 0x{security_seed >> 8:02X};",
                    f"  DiagRequest.byte(4) = 0x{security_seed & 0xFF:02X};",
                    f"  output(DiagRequest);",
                    f"  testWaitForTimeout({tc['timeout_ms']});",
                ])

            lines.extend([
                f"  // Execute {name}",
                f"  DiagRequest.byte(0) = 0x01;",
                f"  DiagRequest.byte(1) = 0x{sid:02X};  // SID: {name}",
                f"  output(DiagRequest);",
                f"  testWaitForTimeout({tc['timeout_ms']});",
                "",
            ])

        lines.extend([
            "  write(\"=== UDS Diagnostic Test Completed ===\");",
            "}",
        ])

        return "\n".join(lines)
