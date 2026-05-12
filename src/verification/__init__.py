"""
Verification Package

Provides closed-loop verification capabilities through CANoe simulation.
"""

from .canoe_interface import CANoeInterface, CANoeConfig, SimulationResult
from .comparator import BusDataComparator, ComparisonReport, SignalComparison, ComparisonResult
from .simulator import SimulationController, VerificationStep, VerificationReport

__all__ = [
    "CANoeInterface",
    "CANoeConfig",
    "SimulationResult",
    "BusDataComparator",
    "ComparisonReport",
    "SignalComparison",
    "ComparisonResult",
    "SimulationController",
    "VerificationStep",
    "VerificationReport",
]
