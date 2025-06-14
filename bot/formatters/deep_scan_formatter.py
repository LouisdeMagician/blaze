# Rebuild entire formatter with detailed report generation

from typing import Dict, List, Any, Tuple


class _KVFormatter:
    """Utility class for rendering primitive key/value pairs."""

    @staticmethod
    def lines(data: Dict[str, Any], *, indent: str = "  ") -> List[str]:
        out: List[str] = []
        for key, val in data.items():
            # skip verbose nested structures
            if isinstance(val, (dict, list)):
                continue
            # shorten floats
            if isinstance(val, float):
                val = round(val, 4)
            out.append(f"{indent}• *{key}*: `{val}`")
        return out


def format_deep_scan_result(result: Dict[str, Any]) -> str:
    """Convert orchestrator output into a **rich, human-readable** markdown report.

    This avoids raw JSON blocks and instead presents each analyzer's findings in
    a structured way.
    """

    token: str = result.get("token_address", "Unknown")
    duration: float = result.get("scan_duration_sec", 0)
    depth: str = result.get("depth", "deep")

    lines: List[str] = []
    lines.append(f"*📊 Deep Scan Report*  \#`{token}`")
    lines.append("════════════════════════")
    lines.append(f"_Depth_: *{depth}* | _Duration_: *{duration}s*\n")

    # Quick risk overview
    overall_risks: List[Tuple[str, Any]] = []
    for mod in result.get("modules", []):
        res = mod.get("result")
        if isinstance(res, dict):
            risk = res.get("risk_level")
        elif hasattr(res, "risk_level"):
            risk = getattr(res, "risk_level", None)
        else:
            risk = None
        if risk:
            overall_risks.append((mod["module"], risk))

    if overall_risks:
        risk_summary = ", ".join([f"{m}:{r}" for m, r in overall_risks])
        lines.append(f"*Risk overview*: {risk_summary}\n")

    # Detailed per-module section
    for mod in result.get("modules", []):
        name = mod.get("module", "unknown").replace("_", " ").title()
        lines.append(f"*{name}*:")
        if mod.get("success"):
            res = mod.get("result")
            if isinstance(res, dict):
                # Hide internal sentinel keys like healthy_liquidity
                filtered = {k: v for k, v in res.items() if k != "healthy_liquidity"}
                lines.extend(_KVFormatter.lines(filtered))
                explanation = res.get("explanation")
                if explanation:
                    lines.append(f"  _{explanation}_")
            else:
                # Attempt to serialise known models (e.g., AnalysisResult)
                if hasattr(res, "to_dict") and callable(getattr(res, "to_dict")):
                    obj_dict = res.to_dict()
                    lines.extend(_KVFormatter.lines(obj_dict))
                    explanation = obj_dict.get("summary") or obj_dict.get("explanation")
                    if explanation:
                        lines.append(f"  _{explanation}_")
                elif hasattr(res, "get_formatted_summary"):
                    lines.append(res.get_formatted_summary())
                else:
                    # Fallback – render as string
                    lines.append(f"  `{str(res)}`")
                explanation = None
        else:
            lines.append(f"  ❌ *Error*: `{mod.get('error')}`")
        lines.append("")

    lines.append("_End of report_")
    return "\n".join(lines) 