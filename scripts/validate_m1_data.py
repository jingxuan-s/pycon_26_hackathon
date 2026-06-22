"""Validate M1 normalized jobs-skills data outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "processed"

REQUIRED_FILES = {
    "roles": OUTPUT_DIR / "roles.csv",
    "skills": OUTPUT_DIR / "skills.csv",
    "role_skill_requirements": OUTPUT_DIR / "role_skill_requirements.csv",
    "skill_ka_items": OUTPUT_DIR / "skill_ka_items.csv",
    "data_quality_report": OUTPUT_DIR / "data_quality_report.md",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(REQUIRED_FILES[name], low_memory=False)


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES.values() if not path.exists()]
    require(not missing, f"Missing M1 output files: {missing}")

    roles = load_csv("roles")
    skills = load_csv("skills")
    requirements = load_csv("role_skill_requirements")
    ka_items = load_csv("skill_ka_items")
    report_text = REQUIRED_FILES["data_quality_report"].read_text(encoding="utf-8")

    require(len(roles) > 0, "roles.csv must contain rows")
    require(len(skills) > 0, "skills.csv must contain rows")
    require(len(requirements) > 0, "role_skill_requirements.csv must contain rows")
    require(len(ka_items) > 0, "skill_ka_items.csv must contain rows")

    role_skill_trace_cols = [
        "role_skill_requirement_id",
        "role_id",
        "skill_id",
        "required_level",
        "skill_weight",
        "sector",
        "track",
        "job_role",
        "unique_skill_title",
        "tsc_ccs_code",
        "tsc_ccs_title",
        "proficiency_level_raw",
        "proficiency_description",
        "source_file",
        "source_sheet",
        "source_row_number",
    ]
    ka_trace_cols = [
        "skill_ka_item_id",
        "skill_id",
        "unique_skill_title",
        "tsc_ccs_code",
        "tsc_ccs_title",
        "proficiency_level",
        "ka_classification",
        "ka_item",
        "source_file",
        "source_sheet",
        "source_row_number",
    ]

    for col in role_skill_trace_cols:
        require(col in requirements.columns, f"Missing role-skill trace column: {col}")
    for col in ka_trace_cols:
        require(col in ka_items.columns, f"Missing K&A trace column: {col}")

    require(requirements["role_id"].notna().all(), "All role-skill rows must resolve to a role_id")
    require(requirements["skill_id"].notna().all(), "All role-skill rows must resolve to a skill_id")
    require(requirements["required_level"].notna().all(), "All role-skill rows must have a required_level")
    require((requirements["skill_weight"] == 1.0).all(), "All MVP skill weights must be 1.0")
    require(ka_items["skill_id"].notna().any(), "K&A rows must include mapped skill_id values")

    has_data_analyst = requirements["job_role"].str.contains("Data Analyst", case=False, na=False).any()
    has_data_scientist = requirements["job_role"].str.contains("Data Scientist", case=False, na=False).any()
    require(has_data_analyst, "Data Analyst sample profile must exist in role-skill requirements")
    require(has_data_scientist, "Data Scientist sample profile must exist in role-skill requirements")

    for required_phrase in [
        "Role-skill rows matched to roles",
        "Role-skill rows matched to unique skills",
        "Role-skill rows with matching K&A items",
        "Role-skill rows with text proficiency levels normalized",
        "Sample Data Analyst Profile Rows",
        "Sample Data Scientist Profile Rows",
    ]:
        require(required_phrase in report_text, f"Data quality report missing section: {required_phrase}")

    print("M1 validation passed")
    print(f"roles={len(roles)}")
    print(f"skills={len(skills)}")
    print(f"role_skill_requirements={len(requirements)}")
    print(f"skill_ka_items={len(ka_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
