"""
Multi-Agent Collaboration Package

Provides the four sub-agents that form the automated testing pipeline:
1. DBCParseAgent - DBC parsing and validation
2. SignalReasonerAgent - Signal dependency analysis
3. CAPLGeneratorAgent - CAPL script generation
4. VerificationAgent - Closed-loop verification and reporting
"""

from .dbc_parser_agent import DBCParseAgent
from .signal_reasoner_agent import SignalReasonerAgent
from .capl_generator_agent import CAPLGeneratorAgent
from .verification_agent import VerificationAgent

__all__ = [
    "DBCParseAgent",
    "SignalReasonerAgent",
    "CAPLGeneratorAgent",
    "VerificationAgent",
]
