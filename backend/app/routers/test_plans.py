"""Test Plans + Test Execution + Load Testing."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    LoadTest, Project, TestCase, TestPlan, TestResult, TestRun, TestSuite,
    User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["test plans, execution, load testing"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Test Plans ──────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/test-plans")
def list_test_plans(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    plans = db.scalars(select(TestPlan).where(TestPlan.project_id == pid).order_by(TestPlan.created_at.desc())).all()
    return [{"id": p.id, "name": p.name, "description": p.description, "state": p.state} for p in plans]


class PlanCreate(BaseModel):
    name: str
    description: str = ""


@router.post("/api/projects/{pid}/test-plans", status_code=201)
def create_test_plan(pid: int, payload: PlanCreate,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    plan = TestPlan(project_id=pid, name=payload.name, description=payload.description, created_by=user.id)
    db.add(plan)
    db.flush()
    db.add(TestSuite(plan_id=plan.id, name="Default Suite"))
    db.commit()
    return {"id": plan.id, "name": plan.name}


# ── Test Suites ─────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/test-plans/{plan_id}/suites")
def list_suites(pid: int, plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    suites = db.scalars(select(TestSuite).where(TestSuite.plan_id == plan_id)).all()
    result = []
    for s in suites:
        count = db.scalar(select(func.count(TestCase.id)).where(TestCase.suite_id == s.id)) or 0
        result.append({"id": s.id, "name": s.name, "case_count": count})
    return result


class SuiteCreate(BaseModel):
    name: str


@router.post("/api/projects/{pid}/test-plans/{plan_id}/suites", status_code=201)
def create_suite(pid: int, plan_id: int, payload: SuiteCreate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    s = TestSuite(plan_id=plan_id, name=payload.name)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name}


# ── Test Cases ──────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/test-suites/{suite_id}/cases")
def list_cases(pid: int, suite_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    cases = db.scalars(select(TestCase).where(TestCase.suite_id == suite_id).order_by(TestCase.created_at.desc())).all()
    return [{"id": c.id, "title": c.title, "priority": c.priority, "state": c.state} for c in cases]


class CaseCreate(BaseModel):
    title: str
    description: str = ""
    steps: str = ""
    priority: str = "medium"


@router.post("/api/projects/{pid}/test-suites/{suite_id}/cases", status_code=201)
def create_case(pid: int, suite_id: int, payload: CaseCreate,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    case = TestCase(suite_id=suite_id, title=payload.title, description=payload.description,
                    steps=payload.steps, priority=payload.priority)
    db.add(case)
    db.commit()
    return {"id": case.id, "title": case.title}


@router.patch("/api/projects/{pid}/test-cases/{case_id}")
def update_case(pid: int, case_id: int, payload: CaseCreate,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    case = db.get(TestCase, case_id)
    if case is None:
        raise HTTPException(404, "Not found")
    case.title = payload.title
    case.description = payload.description
    case.steps = payload.steps
    case.priority = payload.priority
    db.commit()
    return {"ok": True}


# ── Test Runs ───────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/test-runs")
def list_test_runs(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    runs = db.scalars(select(TestRun).where(TestRun.project_id == pid).order_by(TestRun.created_at.desc()).limit(20)).all()
    return [{"id": r.id, "name": r.name, "state": r.state, "total": r.total,
             "passed": r.passed, "failed": r.failed, "skipped": r.skipped} for r in runs]


class RunCreate(BaseModel):
    name: str
    plan_id: int | None = None


@router.post("/api/projects/{pid}/test-runs", status_code=201)
def create_test_run(pid: int, payload: RunCreate,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    run = TestRun(project_id=pid, plan_id=payload.plan_id, name=payload.name)
    db.add(run)
    db.commit()
    return {"id": run.id, "name": run.name}


class ResultSubmit(BaseModel):
    test_case_id: int
    outcome: str  # passed | failed | blocked | skipped
    comment: str = ""


@router.post("/api/projects/{pid}/test-runs/{run_id}/results", status_code=201)
def submit_result(pid: int, run_id: int, payload: ResultSubmit,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    run = db.get(TestRun, run_id)
    if run is None or run.project_id != pid:
        raise HTTPException(404, "Not found")
    result = TestResult(test_case_id=payload.test_case_id, run_id=run_id,
                        outcome=payload.outcome, comment=payload.comment,
                        executed_by=user.id, executed_at=utcnow())
    db.add(result)
    run.total += 1
    if payload.outcome == "passed":
        run.passed += 1
    elif payload.outcome == "failed":
        run.failed += 1
    elif payload.outcome == "skipped":
        run.skipped += 1
    db.commit()
    return {"id": result.id, "outcome": result.outcome}


@router.post("/api/projects/{pid}/test-runs/{run_id}/complete")
def complete_test_run(pid: int, run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    run = db.get(TestRun, run_id)
    if run is None or run.project_id != pid:
        raise HTTPException(404, "Not found")
    run.state = "completed"
    run.completed_at = utcnow()
    db.commit()
    return {"ok": True, "total": run.total, "passed": run.passed, "failed": run.failed}


# ── Load Testing ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/load-tests")
def list_load_tests(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    tests = db.scalars(select(LoadTest).where(LoadTest.project_id == pid).order_by(LoadTest.created_at.desc())).all()
    return [{"id": t.id, "name": t.name, "target_url": t.target_url, "concurrent_users": t.concurrent_users,
             "duration_s": t.duration_s, "status": t.status} for t in tests]


class LoadTestCreate(BaseModel):
    name: str
    target_url: str
    concurrent_users: int = 10
    duration_s: int = 60


@router.post("/api/projects/{pid}/load-tests", status_code=201)
def create_load_test(pid: int, payload: LoadTestCreate,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    test = LoadTest(project_id=pid, name=payload.name, target_url=payload.target_url,
                    concurrent_users=payload.concurrent_users, duration_s=payload.duration_s,
                    created_by=user.id)
    db.add(test)
    db.commit()
    return {"id": test.id, "name": test.name, "status": test.status}


@router.post("/api/projects/{pid}/load-tests/{tid}/run")
def run_load_test(pid: int, tid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    test = db.get(LoadTest, tid)
    if test is None or test.project_id != pid:
        raise HTTPException(404, "Not found")
    test.status = "running"
    db.commit()
    return {"ok": True, "status": test.status}
