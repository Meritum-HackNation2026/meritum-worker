"""Steps of the erasure scenario in features/notifications.feature.

The plan of a recheck run and its child workflow sit in the in-memory workflow
store as DBOS keeps them; `delete_subject` runs on in-memory repositories. No
DBOS, no database.
"""

import asyncio
import json

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.jobs.contracts import CHECK, CheckInput
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.shared.database import DatabaseSettings
from recheck_support import (
    ASKED_AT,
    CLAIM,
    OLD_CHECK,
    SCHEDULED,
    new_passage,
    old_record,
    store_with_new_document,
)

from meritum_worker.checks import FakeCorpusSearch
from meritum_worker.moderation import InMemoryCheckResults
from meritum_worker.notifications import (
    RECHECK_CLAIM_WORKFLOW,
    RECHECK_WORKFLOW,
    RecheckDeps,
    plan_rechecks,
)
from meritum_worker.security import (
    InMemoryWorkflowStore,
    build_retention_deps,
    erase_subject,
)

RUN = "recheck-run-1"


@given('plan ponownych sprawdzeń wymienia sesję "{session}"')
def plan_names_session(context: Context, session: str) -> None:
    context.workflows = InMemoryWorkflowStore()
    context.erasure = build_retention_deps(
        DatabaseSettings(provider="memory"),
        None,
        workflows=context.workflows,
        check_workflows=(CHECK.name,),
        recheck_workflows=(RECHECK_CLAIM_WORKFLOW,),
    )
    records = context.erasure.app.records
    asyncio.run(records.save(old_record(session)))
    asker = CheckInput(
        request=CheckRequest(channel="web", text=CLAIM),
        session_id=session,
        received_at=ASKED_AT,
    ).model_dump(mode="json")
    context.workflows.add(OLD_CHECK, CHECK.name, asker, created_at=ASKED_AT)
    results = InMemoryCheckResults()
    results.add(OLD_CHECK, ASKED_AT, [(CLAIM, True)])
    deps = RecheckDeps(
        results=results,
        records=records,
        corpus=FakeCorpusSearch([new_passage()]),
        snapshots=store_with_new_document(),
        inbox=InMemoryNotificationRepository(),
    )
    plans = asyncio.run(plan_rechecks(SCHEDULED, deps, SCHEDULED))
    assert len(plans) == 1
    # The run keeps its plan step's output; each recheck is a child workflow.
    dumped = [plan.model_dump(mode="json") for plan in plans]
    context.workflows.add(RUN, RECHECK_WORKFLOW, {"plan": dumped}, created_at=SCHEDULED)
    for plan in dumped:
        context.workflows.add(
            plan["check_id"], RECHECK_CLAIM_WORKFLOW, plan, created_at=SCHEDULED
        )


@when('backend zleca delete_subject dla "{session}"')
def erase_session(context: Context, session: str) -> None:
    payload = {"kind": "session_id", "value": session}
    asyncio.run(erase_subject(payload, context.erasure))


@then('w DBOS nie zostaje żaden zapis z "{session}"')
def nothing_names_session(context: Context, session: str) -> None:
    assert session not in json.dumps(context.workflows.payloads())
    # A recheck's steps read the asker from the record, so it goes with the person.
    assert context.workflows.ids() == {RUN}
