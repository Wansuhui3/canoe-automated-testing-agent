"""
Report Generation Package

Provides standardized test report generation in HTML and JSON formats.
"""

from .generator import ReportGenerator, ReportMetadata

__all__ = [
    "ReportGenerator",
    "ReportMetadata",
]
