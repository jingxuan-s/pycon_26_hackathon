"""Validate the interactive local questionnaire with scripted terminal inputs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobs_skills.local_questionnaire import LocalQuestionnaireRunner


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    os.environ["EXPLAINER_AGENT_DISABLED"] = "1"
    # 1 = Data Analyst current role, 10 baseline answers at level 3/4 as allowed,
    # choose the Data Scientist recommendation in the default ranking, then answer follow-up questions at level 3.
    scripted_inputs = iter([
        "1",
        "4", "3", "3", "3", "3", "3", "3", "3", "3", "3",
        "3",
        "3", "3", "3", "3", "3",
    ])
    output_lines: list[str] = []

    def input_func(prompt: str) -> str:
        output_lines.append(prompt)
        return next(scripted_inputs)

    runner = LocalQuestionnaireRunner(PROJECT_ROOT, input_func=input_func, output_func=output_lines.append)
    result = runner.run()

    require(result.baseline_answer_count == 10, "Local questionnaire must record 10 baseline answers")
    require(result.followup_answer_count == 5, "Local questionnaire must record 5 follow-up answers")
    require(result.report_path.exists(), "Local questionnaire must write a result report")
    require(result.suitability_percentage > 0, "Local questionnaire must produce a positive suitability score")
    require(any("Recommended pathways" in line for line in output_lines), "Local questionnaire must show recommendations")
    require(any("Explanation source:" in line for line in output_lines), "Local questionnaire must show explainer source")
    require(any("Assessment result" in line for line in output_lines), "Local questionnaire must show final result")

    print("Local questionnaire validation passed")
    print(f"suitability_percentage={result.suitability_percentage:.2f}")
    print(f"pathway_fit_percentage={result.pathway_fit_percentage:.2f}")
    print(f"report={result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
