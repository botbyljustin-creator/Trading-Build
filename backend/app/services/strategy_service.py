"""Strategy Architect / Strategy Auditor / Code Generator orchestration
(ARCHITECTURE.md §5.5-7, §7). This is where the rule-status gate in
`app.models.enums.COMPILABLE_RULE_STATUSES` is actually enforced against
the database — `app.strategy.compiler` itself just trusts its input."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC

from sqlalchemy.orm import Session

from app.codegen.pine import generate_pine_script
from app.codegen.python_gen import generate_python_strategy
from app.models.enums import (
    COMPILABLE_RULE_STATUSES,
    CodeLanguage,
    RuleStatus,
    StrategyVersionStatus,
)
from app.models.rule import Rule
from app.models.strategy import GeneratedCode, Strategy, StrategySpec, StrategyVersion
from app.schemas.strategy_spec import StrategySpecification
from app.services.contradiction_service import has_unresolved_contradiction
from app.strategy.compilable_rule import CompilableRule
from app.strategy.compiler import compile_strategy
from app.strategy.completeness import check_completeness
from app.strategy.versioning import diff_specs


class RulesNotCompilableError(ValueError):
    def __init__(self, offending: dict[str, str]):
        self.offending = offending
        super().__init__(
            "The following rules are not eligible for compilation (must be "
            f"USER_CONFIRMED or USER_MODIFIED first): {offending}"
        )


class UnresolvedContradictionsError(ValueError):
    def __init__(self, contradiction_ids: list[str]):
        self.contradiction_ids = contradiction_ids
        super().__init__(f"Resolve these contradictions before compiling: {contradiction_ids}")


def compile_strategy_version(
    db: Session, strategy: Strategy, rule_ids: list[uuid.UUID]
) -> StrategyVersion:
    rules = (
        db.query(Rule).filter(Rule.id.in_(rule_ids), Rule.project_id == strategy.project_id).all()
    )
    found_ids = {r.id for r in rules}
    missing_ids = set(rule_ids) - found_ids
    if missing_ids:
        raise ValueError(f"Rule ids not found in this project: {missing_ids}")

    offending = {
        str(r.id): r.status.value for r in rules if r.status not in COMPILABLE_RULE_STATUSES
    }
    if offending:
        raise RulesNotCompilableError(offending)

    unresolved = has_unresolved_contradiction(db, list(found_ids))
    if unresolved:
        raise UnresolvedContradictionsError([str(c.id) for c in unresolved])

    compilable = [
        CompilableRule(
            id=str(r.id),
            category=r.category,
            natural_language_rule=r.natural_language_rule,
            machine_readable_rule=r.machine_readable_rule,
            confidence=r.confidence,
        )
        for r in rules
    ]
    spec = compile_strategy(strategy.name, compilable)
    completeness = check_completeness(spec)

    previous_version = (
        db.query(StrategyVersion)
        .filter(StrategyVersion.strategy_id == strategy.id)
        .order_by(StrategyVersion.version_number.desc())
        .first()
    )
    previous_spec = None
    if previous_version is not None and previous_version.spec is not None:
        previous_spec = StrategySpecification.model_validate(previous_version.spec.spec_json)
    changes = diff_specs(previous_spec, spec)
    change_summary = (
        "Initial version."
        if previous_spec is None
        else f"Changed fields: {', '.join(changes.keys()) or 'none'}."
    )

    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=(previous_version.version_number + 1 if previous_version else 1),
        label=f"v{(previous_version.version_number + 1 if previous_version else 1)}",
        change_summary=change_summary,
        status=StrategyVersionStatus.COMPILED,
        completeness_score=completeness.score_pct,
        missing_fields=completeness.missing,
        rule_ids=[str(r.id) for r in rules],
    )
    db.add(version)
    db.flush()
    db.add(StrategySpec(strategy_version_id=version.id, spec_json=spec.model_dump(mode="json")))
    db.commit()
    db.refresh(version)
    return version


def generate_code_for_version(db: Session, version: StrategyVersion) -> list[GeneratedCode]:
    if version.spec is None:
        raise ValueError("This strategy version has no compiled specification yet.")
    spec = StrategySpecification.model_validate(version.spec.spec_json)

    pine_code = generate_pine_script(spec, version.label or f"v{version.version_number}")
    python_code = generate_python_strategy(spec, version.label or f"v{version.version_number}")

    results = []
    for language, code in [(CodeLanguage.PINE, pine_code), (CodeLanguage.PYTHON, python_code)]:
        spec_hash = hashlib.sha256(
            json.dumps(spec.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        existing = (
            db.query(GeneratedCode)
            .filter(
                GeneratedCode.strategy_version_id == version.id, GeneratedCode.language == language
            )
            .one_or_none()
        )
        if existing is not None:
            existing.code = code
            existing.spec_hash = spec_hash
            results.append(existing)
        else:
            row = GeneratedCode(
                strategy_version_id=version.id, language=language, code=code, spec_hash=spec_hash
            )
            db.add(row)
            results.append(row)
    db.commit()
    return results


def approve_rule(db: Session, rule: Rule, user_id: uuid.UUID) -> Rule:
    from datetime import datetime

    rule.status = RuleStatus.USER_CONFIRMED
    rule.reviewed_by_user_id = user_id
    rule.reviewed_at = datetime.now(UTC)
    db.commit()
    return rule
