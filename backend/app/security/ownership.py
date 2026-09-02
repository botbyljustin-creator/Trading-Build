"""Per-request ownership checks shared by every route that hangs off a
project, directly or transitively. Every dependency here returns 404
(never 403) when the row exists but isn't reachable from the caller's own
projects, so an authenticated user can't even confirm another user's data
exists (Module: Security — user data isolation)."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.backtest import Backtest
from app.models.job import Job
from app.models.project import Project
from app.models.report import Report
from app.models.rule import Contradiction, Rule, RuleQuantification
from app.models.source import Source, Video
from app.models.strategy import Strategy, StrategyVersion
from app.models.user import User
from app.security.clerk import get_current_user

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


def get_owned_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if project is None:
        raise _NOT_FOUND
    return project


def get_owned_source(
    source_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Source:
    source = (
        db.query(Source)
        .join(Project, Project.id == Source.project_id)
        .filter(Source.id == source_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if source is None:
        raise _NOT_FOUND
    return source


def get_owned_video(
    video_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Video:
    video = (
        db.query(Video)
        .join(Project, Project.id == Video.project_id)
        .filter(Video.id == video_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if video is None:
        raise _NOT_FOUND
    return video


def get_owned_rule(
    rule_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Rule:
    rule = (
        db.query(Rule)
        .join(Project, Project.id == Rule.project_id)
        .filter(Rule.id == rule_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if rule is None:
        raise _NOT_FOUND
    return rule


def get_owned_rule_quantification(
    quantification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RuleQuantification:
    quantification = (
        db.query(RuleQuantification)
        .join(Rule, Rule.id == RuleQuantification.rule_id)
        .join(Project, Project.id == Rule.project_id)
        .filter(RuleQuantification.id == quantification_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if quantification is None:
        raise _NOT_FOUND
    return quantification


def get_owned_contradiction(
    contradiction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Contradiction:
    contradiction = (
        db.query(Contradiction)
        .join(Project, Project.id == Contradiction.project_id)
        .filter(Contradiction.id == contradiction_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if contradiction is None:
        raise _NOT_FOUND
    return contradiction


def get_owned_strategy(
    strategy_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Strategy:
    strategy = (
        db.query(Strategy)
        .join(Project, Project.id == Strategy.project_id)
        .filter(Strategy.id == strategy_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if strategy is None:
        raise _NOT_FOUND
    return strategy


def get_owned_strategy_version(
    version_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> StrategyVersion:
    version = (
        db.query(StrategyVersion)
        .join(Strategy, Strategy.id == StrategyVersion.strategy_id)
        .join(Project, Project.id == Strategy.project_id)
        .filter(StrategyVersion.id == version_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if version is None:
        raise _NOT_FOUND
    return version


def get_owned_backtest(
    backtest_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Backtest:
    backtest = (
        db.query(Backtest)
        .join(StrategyVersion, StrategyVersion.id == Backtest.strategy_version_id)
        .join(Strategy, Strategy.id == StrategyVersion.strategy_id)
        .join(Project, Project.id == Strategy.project_id)
        .filter(Backtest.id == backtest_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if backtest is None:
        raise _NOT_FOUND
    return backtest


def get_owned_job(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Job:
    job = (
        db.query(Job)
        .join(Project, Project.id == Job.project_id)
        .filter(Job.id == job_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if job is None:
        raise _NOT_FOUND
    return job


def get_owned_report(
    report_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Report:
    report = (
        db.query(Report)
        .join(StrategyVersion, StrategyVersion.id == Report.strategy_version_id)
        .join(Strategy, Strategy.id == StrategyVersion.strategy_id)
        .join(Project, Project.id == Strategy.project_id)
        .filter(Report.id == report_id, Project.owner_id == user.id)
        .one_or_none()
    )
    if report is None:
        raise _NOT_FOUND
    return report
