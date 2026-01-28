#!/usr/bin/env python3
import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

ALLOWED_STATUSES = ["not started", "work in progress", "complete", "to be updated"]

DETAIL_HEADINGS = [
    "# Section",
    "## Summary",
    "## Design",
    "## Implementation Steps",
    "## Risks",
    "## Dependencies",
    "## Acceptance Criteria",
]


@dataclass
class Section:
    section_id: str
    title: str
    status: str
    summary: str
    details_markdown: str


@dataclass
class PlanResult:
    project_title: str
    scope_classification: str
    overview: str
    sections: List[Section]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"^-+|-+$", "", value)
    return value or "section"


def load_input_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_schema() -> Dict[str, Any]:
    return {
        "name": "overview_plan",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "project_title": {"type": "string"},
                "scope_classification": {"type": "string"},
                "overview": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "status": {"type": "string", "enum": ALLOWED_STATUSES},
                            "summary": {"type": "string"},
                            "details_markdown": {"type": "string"},
                        },
                        "required": ["id", "title", "status", "summary", "details_markdown"],
                    },
                },
            },
            "required": ["project_title", "scope_classification", "overview", "sections"],
        },
        "strict": True,
    }


def build_detail_prompt(section_title: str) -> str:
    headings = "\n".join(DETAIL_HEADINGS)
    return (
        "You are validating and enriching a detailed implementation plan section. "
        "Keep the structure and headings exactly as shown below. "
        "Fill in missing details, remove contradictions, and ensure the plan is actionable. "
        "Return the full updated section in Markdown, preserving the headings.\n\n"
        f"Required headings:\n{headings}\n\n"
        f"Section title: {section_title}"
    )


def normalize_detail_markdown(section_title: str, content: str) -> str:
    if content.strip().startswith("# Section"):
        return content.strip() + "\n"

    body = content.strip()
    return (
        f"# Section\n"
        f"{section_title}\n\n"
        f"## Summary\n\n"
        f"## Design\n\n"
        f"## Implementation Steps\n\n"
        f"## Risks\n\n"
        f"## Dependencies\n\n"
        f"## Acceptance Criteria\n\n"
        f"{body}\n"
    )


def parse_plan(data: Dict[str, Any]) -> PlanResult:
    sections = []
    for item in data.get("sections", []):
        sections.append(
            Section(
                section_id=str(item["id"]),
                title=str(item["title"]),
                status=str(item["status"]),
                summary=str(item["summary"]),
                details_markdown=str(item["details_markdown"]),
            )
        )
    return PlanResult(
        project_title=str(data["project_title"]),
        scope_classification=str(data["scope_classification"]),
        overview=str(data["overview"]),
        sections=sections,
    )


def write_overview(plan: PlanResult, output_path: Path) -> None:
    lines = [
        f"# {plan.project_title}",
        "",
        f"Scope classification: {plan.scope_classification}",
        "",
        "## Overview",
        plan.overview,
        "",
        "## Sections",
        "",
    ]
    for section in plan.sections:
        lines.extend(
            [
                f"### {section.section_id}: {section.title}",
                f"Status: {section.status}",
                "",
                section.summary,
                "",
            ]
        )
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_section_detail(section: Section, output_dir: Path) -> Path:
    filename = f"{section.section_id}-{slugify(section.title)}.md"
    path = output_dir / filename
    content = normalize_detail_markdown(section.title, section.details_markdown)
    path.write_text(content, encoding="utf-8")
    return path


def _create_text_response(client: OpenAI, model: str, instructions: str, user_input: str, json_schema: Dict[str, Any] | None = None) -> str:
    if hasattr(client, "responses"):
        kwargs: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": user_input,
        }
        if json_schema is not None:
            kwargs["text"] = {"format": {"type": "json_schema", **json_schema}}
        response = client.responses.create(**kwargs)
        if not response.output_text:
            raise RuntimeError("Model returned empty output.")
        return response.output_text

    # Fallback for older SDKs that don't expose Responses API.
    if json_schema is not None:
        user_input = (
            f"Return JSON that strictly matches this schema:\n{json.dumps(json_schema['schema'])}\n\n"
            + user_input
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
        )
    else:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_input},
            ],
        )
    content = response.choices[0].message.content if response.choices else ""
    if not content:
        raise RuntimeError("Model returned empty output.")
    return content


def run_overview_plan(client: OpenAI, model: str, design_text: str) -> PlanResult:
    schema = build_schema()
    system_prompt = (
        "You are a product and engineering planner. "
        "Design an implementation plan from the given project design. "
        "If scope is unclear, classify the plan as '4 week MVP'. "
        "Create clear, distinct sections suitable for streamlined implementation."
    )
    user_prompt = (
        "Project design:\n" + design_text.strip() + "\n\n" +
        "Return JSON that matches the provided schema. "
        "Each section must include a concise summary and a detailed markdown plan."
    )

    raw = _create_text_response(client, model, system_prompt, user_prompt, schema)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse model output as JSON: {exc}") from exc

    if not data.get("scope_classification"):
        data["scope_classification"] = "4 week mvp"

    return parse_plan(data)


def run_detail_validation(client: OpenAI, model: str, section_title: str, detail_text: str) -> str:
    prompt = build_detail_prompt(section_title)
    output = _create_text_response(client, model, prompt, detail_text)
    return output.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate overview and detailed plans from a project design.")
    parser.add_argument("input_file", help="Path to the project design file.")
    parser.add_argument("--output-dir", default="docs", help="Output directory for plan files.")
    parser.add_argument("--overview-model", default="gpt-5.2", help="Model for overview plan generation.")
    parser.add_argument("--detail-model", default="gpt-5-mini", help="Model for detail validation.")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_dir = Path(args.output_dir)
    sections_dir = output_dir / "sections"
    ensure_dir(sections_dir)

    design_text = load_input_text(input_path)
    client = OpenAI()

    plan = run_overview_plan(client, args.overview_model, design_text)

    overview_path = output_dir / "overview_plan.md"
    write_overview(plan, overview_path)
    print(f"Wrote overview: {overview_path}")

    total_sections = len(plan.sections)
    for index, section in enumerate(plan.sections, start=1):
        print(f"[{index}/{total_sections}] Generating section: {section.section_id} - {section.title}")
        detail_path = write_section_detail(section, sections_dir)
        refined = run_detail_validation(
            client,
            args.detail_model,
            section.title,
            detail_path.read_text(encoding="utf-8"),
        )
        detail_path.write_text(refined, encoding="utf-8")

    print(f"Wrote {len(plan.sections)} detailed section files in {sections_dir}")


if __name__ == "__main__":
    main()
