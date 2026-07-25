import json
from typing import Any

from app.models import Analysis


def analysis_export_dict(analysis: Analysis) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "name": analysis.name,
        "target": {
            "job_title": analysis.job_description.title,
            "employer": analysis.job_description.employer,
            "location": analysis.job_description.location,
        },
        "analysis_date": analysis.updated_at.isoformat(),
        "state": analysis.state,
        "overall_score": analysis.overall_score,
        "model_status": analysis.model_status,
        "summary": analysis.result,
        "scores": [
            {
                "category": item.category,
                "score": item.score,
                "maximum": item.maximum,
                "reason": item.reason,
                "improvements": item.improvements,
            }
            for item in analysis.scores
        ],
        "evidence": [
            {
                "requirement": item.requirement,
                "status": item.status,
                "resume_excerpt": item.resume_excerpt,
                "source_section": item.source_section,
                "confidence": item.confidence,
                "interpretation": item.interpretation,
            }
            for item in analysis.evidence
        ],
        "recommendations": [
            {
                "priority": item.priority,
                "title": item.title,
                "explanation": item.explanation,
                "supporting_evidence": item.supporting_evidence,
                "role_reason": item.role_reason,
                "recommended_action": item.recommended_action,
                "confidence": item.confidence,
                "confirmation_required": item.confirmation_required,
                "source": item.source,
                "status": item.status,
            }
            for item in analysis.recommendations
        ],
        "interview_questions": [
            {
                "category": item.category,
                "question": item.question,
                "talking_points": item.talking_points,
                "resume_evidence": item.resume_evidence,
                "confidence": item.confidence,
                "source": item.source,
            }
            for item in analysis.interview_questions
        ],
        "limitations": [
            "The alignment score does not predict interview or hiring outcomes.",
            "Missing résumé evidence is not proof that a candidate lacks a qualification.",
            "Model-generated content, when enabled, requires human review.",
            *[
                f"Model-reported limitation: {item}"
                for item in analysis.result.get("model_limitations", [])
            ],
        ],
    }


def render_json(analysis: Analysis) -> str:
    return json.dumps(analysis_export_dict(analysis), indent=2, ensure_ascii=False)


def render_markdown(analysis: Analysis) -> str:
    data = analysis_export_dict(analysis)
    target = data["target"]
    lines = [
        f"# MatchCraft report: {data['name']}",
        "",
        f"- **Target role:** {target['job_title'] or 'Not detected'}",
        f"- **Employer:** {target['employer'] or 'Not detected'}",
        f"- **Analysis date:** {data['analysis_date']}",
        f"- **Overall alignment:** {data['overall_score']}/100",
        f"- **AI-assisted stage:** {data['model_status']}",
        "",
        "> This score is a decision-support aid. It does not predict interview or hiring outcomes.",
        "",
        "## Category scores",
        "",
    ]
    for item in data["scores"]:
        lines.extend(
            [
                f"### {item['category']}: {item['score']}/{item['maximum']}",
                "",
                item["reason"],
                "",
            ]
        )
        if item["improvements"]:
            lines.append("Improvements:")
            lines.extend(f"- {improvement}" for improvement in item["improvements"])
            lines.append("")
    lines.extend(["## Strengths", ""])
    strengths = data["summary"].get("top_strengths", [])
    lines.extend(
        [f"- {item}" for item in strengths] or ["- No explicit supported requirements detected."]
    )
    lines.extend(["", "## Gaps", ""])
    gaps = data["summary"].get("top_gaps", [])
    lines.extend(
        [f"- {item}" for item in gaps] or ["- No explicit unsupported requirements detected."]
    )
    # The UI renders transferable experience as a first-class section, and the JSON
    # export already contains it; omitting it made the two exports disagree.
    transferable_experience = data["summary"].get("transferable_experience", [])
    if transferable_experience:
        lines.extend(["", "## Potentially transferable experience", ""])
        lines.extend(f"- {item}" for item in transferable_experience)
    lines.extend(["", "## Requirement evidence", ""])
    for item in data["evidence"]:
        lines.append(f"### {item['requirement']} — {item['status']}")
        lines.append("")
        lines.append(f"- Confidence: {item['confidence']}")
        lines.append(f"- Résumé evidence: {item['resume_excerpt'] or 'None found'}")
        lines.append(f"- Interpretation: {item['interpretation']}")
        lines.append("")
    if data["summary"].get("model_executive_summary"):
        lines.extend(
            [
                "## Model-generated perspective — review required",
                "",
                data["summary"]["model_executive_summary"],
                "",
            ]
        )
        transferable = data["summary"].get("model_transferable_experience", [])
        if transferable:
            lines.append("Model-identified transferable evidence:")
            lines.extend(f"- {item}" for item in transferable)
            lines.append("")
    lines.extend(["## Recommendations", ""])
    for item in data["recommendations"]:
        marker = " — confirmation required" if item["confirmation_required"] else ""
        lines.extend(
            [
                f"### {item['priority']}: {item['title']}{marker}",
                "",
                item["explanation"],
                "",
                f"**Supporting evidence:** {item['supporting_evidence'] or 'None found'}",
                "",
                f"**Role relevance:** {item['role_reason']}",
                "",
                f"**Action:** {item['recommended_action']}",
                "",
                f"**Confidence / source / status:** {item['confidence']} / {item['source']} / {item['status']}",
                "",
            ]
        )
    lines.extend(["## Interview preparation", ""])
    for item in data["interview_questions"]:
        lines.append(f"- **{item['category'].title()}:** {item['question']}")
        lines.append(f"  - Confidence / source: {item['confidence']} / {item['source']}")
        if item["resume_evidence"]:
            lines.append(f"  - Evidence to use: {item['resume_evidence']}")
        for talking_point in item["talking_points"]:
            lines.append(f"  - Talking point: {talking_point}")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in data["limitations"])
    return "\n".join(lines).rstrip() + "\n"
