"""
Test Report Generator

Generates standardized test reports in HTML and JSON formats,
including pass/fail statistics, signal comparison details,
and execution summaries.
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from ..verification.comparator import ComparisonReport, ComparisonResult
from ..verification.simulator import VerificationReport


@dataclass
class ReportMetadata:
    """Report metadata."""
    project_name: str = ""
    test_target: str = ""
    dbc_filename: str = ""
    oem_spec: str = ""
    generated_at: str = ""
    tool_version: str = "1.0.0"


class ReportGenerator:
    """
    Generates standardized test reports.

    Supports:
    - HTML report with styling and charts
    - JSON report for programmatic consumption
    - Console summary
    """

    def __init__(self, metadata: Optional[ReportMetadata] = None) -> None:
        self.metadata = metadata or ReportMetadata()
        self.metadata.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def generate_html(
        self,
        verification_report: VerificationReport,
        comparison_report: Optional[ComparisonReport] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate an HTML test report.

        Args:
            verification_report: Verification execution results
            comparison_report: Signal comparison results (optional, may be embedded in verification)
            output_path: Path to write the HTML file (if None, only returns string)

        Returns:
            HTML report content
        """
        comp = comparison_report or verification_report.comparison_report
        html = self._build_html(verification_report, comp)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        return html

    def generate_json(
        self,
        verification_report: VerificationReport,
        comparison_report: Optional[ComparisonReport] = None,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Generate a JSON test report.

        Args:
            verification_report: Verification execution results
            comparison_report: Signal comparison results
            output_path: Path to write the JSON file

        Returns:
            Report data as dictionary
        """
        comp = comparison_report or verification_report.comparison_report

        report_data = {
            "metadata": asdict(self.metadata),
            "verification": {
                "test_name": verification_report.test_name,
                "steps_total": verification_report.steps_total,
                "steps_passed": verification_report.steps_passed,
                "steps_failed": verification_report.steps_failed,
                "pass_rate": verification_report.pass_rate,
                "is_passed": verification_report.is_passed,
                "execution_time_ms": verification_report.execution_time_ms,
                "errors": verification_report.errors,
            },
            "comparison": None,
        }

        if comp:
            report_data["comparison"] = {
                "total_signals": comp.total_signals,
                "matches": comp.matches,
                "mismatches": comp.mismatches,
                "tolerance_exceeded": comp.tolerance_exceeded,
                "no_data": comp.no_data,
                "pass_rate": comp.pass_rate,
                "signal_results": [
                    {
                        "signal_name": r.signal_name,
                        "message_name": r.message_name,
                        "expected_value": r.expected_value,
                        "actual_value": r.actual_value,
                        "deviation_percent": r.deviation_percent,
                        "result": r.result.value,
                    }
                    for r in comp.signal_results
                ],
            }

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)

        return report_data

    def _build_html(
        self,
        verification_report: VerificationReport,
        comparison_report: Optional[ComparisonReport],
    ) -> str:
        """Build the complete HTML report."""
        pass_rate = verification_report.pass_rate
        status_color = "#28a745" if verification_report.is_passed else "#dc3545"
        status_text = "PASSED" if verification_report.is_passed else "FAILED"

        signal_rows = ""
        if comparison_report:
            for r in comparison_report.signal_results:
                row_color = "#d4edda" if r.result == ComparisonResult.MATCH else "#f8d7da"
                signal_rows += f"""
                <tr style="background-color: {row_color}">
                    <td>{r.message_name}</td>
                    <td>{r.signal_name}</td>
                    <td>{r.expected_value:.4f}</td>
                    <td>{r.actual_value:.4f if r.actual_value is not None else 'N/A'}</td>
                    <td>{r.deviation_percent:.2f}%</td>
                    <td>{r.result.value}</td>
                </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {verification_report.test_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .header .meta {{ font-size: 14px; opacity: 0.8; }}
        .status-badge {{ display: inline-block; padding: 8px 20px; border-radius: 5px; font-weight: bold; font-size: 18px; background: {status_color}; color: white; margin-top: 15px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .card .value {{ font-size: 36px; font-weight: bold; color: #1a1a2e; }}
        .card .label {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .card.pass .value {{ color: #28a745; }}
        .card.fail .value {{ color: #dc3545; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .section h2 {{ font-size: 18px; margin-bottom: 15px; color: #1a1a2e; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th {{ background: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
        .progress-bar {{ height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; margin-top: 10px; }}
        .progress-bar .fill {{ height: 100%; background: {status_color}; border-radius: 10px; transition: width 0.5s; }}
        .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CANoe Automated Testing Report</h1>
            <div class="meta">
                <p>Test: {verification_report.test_name} | Target: {self.metadata.test_target}</p>
                <p>DBC: {self.metadata.dbc_filename} | OEM Spec: {self.metadata.oem_spec}</p>
                <p>Generated: {self.metadata.generated_at}</p>
            </div>
            <div class="status-badge">{status_text}</div>
        </div>

        <div class="cards">
            <div class="card pass">
                <div class="value">{pass_rate:.1%}</div>
                <div class="label">Pass Rate</div>
            </div>
            <div class="card">
                <div class="value">{verification_report.steps_passed}</div>
                <div class="label">Steps Passed</div>
            </div>
            <div class="card fail">
                <div class="value">{verification_report.steps_failed}</div>
                <div class="label">Steps Failed</div>
            </div>
            <div class="card">
                <div class="value">{verification_report.execution_time_ms / 1000:.1f}s</div>
                <div class="label">Execution Time</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="fill" style="width: {pass_rate * 100:.1f}%"></div>
        </div>

        <div class="section">
            <h2>Signal Comparison Details</h2>
            {"<p>No comparison data available</p>" if not comparison_report else f"""
            <table>
                <thead>
                    <tr>
                        <th>Message</th>
                        <th>Signal</th>
                        <th>Expected</th>
                        <th>Actual</th>
                        <th>Deviation</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {signal_rows}
                </tbody>
            </table>
            """}
        </div>

        {"<div class=\"section\"><h2>Errors</h2><ul>" + "".join(f'<li style="color:#dc3545">{e}</li>' for e in verification_report.errors) + "</ul></div>" if verification_report.errors else ""}

        <div class="footer">
            <p>CANoe Automated Testing Agent v{self.metadata.tool_version} | Report generated automatically</p>
        </div>
    </div>
</body>
</html>"""
        return html
