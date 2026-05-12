"""
OEM Specification Rules Engine

Loads and applies OEM-specific naming conventions, service definitions,
and test rules for CAPL script generation.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OEMServiceRule:
    """OEM-specific diagnostic service rule."""
    service_id: int
    service_name: str
    sub_function_required: bool
    security_level: int = 0
    session_required: str = "default"
    timeout_ms: int = 2000
    description: str = ""


@dataclass
class OEMNamingRule:
    """OEM-specific naming convention rule."""
    message_prefix: str = ""
    signal_prefix: str = ""
    node_prefix: str = ""
    max_name_length: int = 32
    separator: str = "_"


@dataclass
class OEMTestRule:
    """OEM-specific test execution rule."""
    default_cycle_time_ms: int = 100
    max_wait_time_ms: int = 5000
    retry_count: int = 3
    tolerance_percent: float = 1.0
    require_response_pending: bool = True


@dataclass
class OEMSpec:
    """Complete OEM specification for test generation."""
    oem_name: str
    naming: OEMNamingRule = field(default_factory=OEMNamingRule)
    test_rules: OEMTestRule = field(default_factory=OEMTestRule)
    services: dict[int, OEMServiceRule] = field(default_factory=dict)

    def get_service(self, service_id: int) -> Optional[OEMServiceRule]:
        return self.services.get(service_id)


class OEMRulesEngine:
    """
    Loads OEM specifications and provides rule-based guidance
    for CAPL script generation.

    Supports loading YAML-based OEM spec files with service definitions,
    naming conventions, and test execution parameters.
    """

    # Built-in OEM specifications for common manufacturers
    BUILTIN_SPECS = {
        "generic": {
            "oem_name": "Generic",
            "naming": {"max_name_length": 32, "separator": "_"},
            "test_rules": {
                "default_cycle_time_ms": 100,
                "max_wait_time_ms": 5000,
                "retry_count": 3,
                "tolerance_percent": 1.0,
            },
            "services": {},
        },
        "bcm_simplified": {
            "oem_name": "BCM_Simplified",
            "naming": {
                "message_prefix": "BCM_",
                "signal_prefix": "Bcm_",
                "max_name_length": 32,
                "separator": "_",
            },
            "test_rules": {
                "default_cycle_time_ms": 50,
                "max_wait_time_ms": 3000,
                "retry_count": 3,
                "tolerance_percent": 0.5,
            },
            "services": {
                0x10: {
                    "service_id": "0x10",
                    "service_name": "DiagnosticSessionControl",
                    "sub_function_required": True,
                    "session_required": "default",
                    "timeout_ms": 2000,
                },
                0x11: {
                    "service_id": "0x11",
                    "service_name": "ECUReset",
                    "sub_function_required": True,
                    "session_required": "default",
                    "timeout_ms": 5000,
                },
                0x22: {
                    "service_id": "0x22",
                    "service_name": "ReadDataByIdentifier",
                    "sub_function_required": False,
                    "session_required": "default",
                    "timeout_ms": 2000,
                },
                0x27: {
                    "service_id": "0x27",
                    "service_name": "SecurityAccess",
                    "sub_function_required": True,
                    "security_level": 1,
                    "session_required": "extended",
                    "timeout_ms": 2000,
                },
                0x2E: {
                    "service_id": "0x2E",
                    "service_name": "WriteDataByIdentifier",
                    "sub_function_required": False,
                    "security_level": 1,
                    "session_required": "extended",
                    "timeout_ms": 2000,
                },
                0x31: {
                    "service_id": "0x31",
                    "service_name": "RoutineControl",
                    "sub_function_required": True,
                    "security_level": 1,
                    "session_required": "extended",
                    "timeout_ms": 5000,
                },
                0x19: {
                    "service_id": "0x19",
                    "service_name": "ReadDTCInformation",
                    "sub_function_required": True,
                    "session_required": "default",
                    "timeout_ms": 3000,
                },
                0x14: {
                    "service_id": "0x14",
                    "service_name": "ClearDTC",
                    "sub_function_required": False,
                    "security_level": 1,
                    "session_required": "extended",
                    "timeout_ms": 3000,
                },
            },
        },
    }

    def __init__(self, spec_path: Optional[str] = None, spec_name: str = "generic") -> None:
        """
        Initialize the OEM rules engine.

        Args:
            spec_path: Path to a YAML OEM specification file
            spec_name: Name of a built-in spec to use as fallback
        """
        self._spec = self._load_spec(spec_path, spec_name)

    def _load_spec(self, spec_path: Optional[str], spec_name: str) -> OEMSpec:
        """Load OEM specification from file or built-in."""
        if spec_path and Path(spec_path).exists():
            with open(spec_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return self._parse_spec(data)

        # Fallback to built-in spec
        builtin = self.BUILTIN_SPECS.get(spec_name, self.BUILTIN_SPECS["generic"])
        return self._parse_spec(builtin)

    def _parse_spec(self, data: dict) -> OEMSpec:
        """Parse a specification dictionary into an OEMSpec object."""
        naming_data = data.get("naming", {})
        naming = OEMNamingRule(
            message_prefix=naming_data.get("message_prefix", ""),
            signal_prefix=naming_data.get("signal_prefix", ""),
            node_prefix=naming_data.get("node_prefix", ""),
            max_name_length=naming_data.get("max_name_length", 32),
            separator=naming_data.get("separator", "_"),
        )

        test_data = data.get("test_rules", {})
        test_rules = OEMTestRule(
            default_cycle_time_ms=test_data.get("default_cycle_time_ms", 100),
            max_wait_time_ms=test_data.get("max_wait_time_ms", 5000),
            retry_count=test_data.get("retry_count", 3),
            tolerance_percent=test_data.get("tolerance_percent", 1.0),
            require_response_pending=test_data.get("require_response_pending", True),
        )

        services = {}
        for sid_str, svc_data in data.get("services", {}).items():
            sid = int(sid_str, 0) if isinstance(sid_str, str) else sid_str
            services[sid] = OEMServiceRule(
                service_id=sid,
                service_name=svc_data.get("service_name", ""),
                sub_function_required=svc_data.get("sub_function_required", False),
                security_level=svc_data.get("security_level", 0),
                session_required=svc_data.get("session_required", "default"),
                timeout_ms=svc_data.get("timeout_ms", 2000),
                description=svc_data.get("description", ""),
            )

        return OEMSpec(
            oem_name=data.get("oem_name", "Unknown"),
            naming=naming,
            test_rules=test_rules,
            services=services,
        )

    @property
    def spec(self) -> OEMSpec:
        """Get the loaded OEM specification."""
        return self._spec

    def get_service_rule(self, service_id: int) -> Optional[OEMServiceRule]:
        """Get the OEM rule for a specific diagnostic service."""
        return self._spec.get_service(service_id)

    def format_message_name(self, base_name: str) -> str:
        """Apply OEM naming convention to a message name."""
        prefix = self._spec.naming.message_prefix
        if prefix and not base_name.startswith(prefix):
            return f"{prefix}{base_name}"
        return base_name

    def format_signal_name(self, base_name: str) -> str:
        """Apply OEM naming convention to a signal name."""
        prefix = self._spec.naming.signal_prefix
        if prefix and not base_name.startswith(prefix):
            return f"{prefix}{base_name}"
        return base_name

    def get_timeout(self, service_id: int) -> int:
        """Get the timeout for a specific service, or default."""
        rule = self.get_service_rule(service_id)
        if rule:
            return rule.timeout_ms
        return self._spec.test_rules.max_wait_time_ms

    def requires_security(self, service_id: int) -> bool:
        """Check if a service requires security access."""
        rule = self.get_service_rule(service_id)
        return rule.security_level > 0 if rule else False

    def requires_extended_session(self, service_id: int) -> bool:
        """Check if a service requires extended diagnostic session."""
        rule = self.get_service_rule(service_id)
        return rule.session_required == "extended" if rule else False
