"""Models of the notifications slice: one planned recheck and the ports it uses.

Features:
    US-POW-03, F-39
"""

from dataclasses import dataclass

from meritum_core.checks import CheckRecordRepository
from meritum_core.corpus import CorpusSearchPort
from meritum_core.notifications import NotificationRepository
from pydantic import BaseModel, ConfigDict

from meritum_worker.moderation import CheckResults
from meritum_worker.notifications.ports import SnapshotReader


class Recheck(BaseModel):
    """One unanswered claim to check again on a new snapshot.

    DBOS keeps it as the plan step's output and as the recheck's input, so it
    never names the asker: ``recheck_input`` reads who asked from the earlier
    record, which ``delete_subject`` erases (US-BEZ-05).

    Attributes:
        old_check_id: the check that left the claim unanswered.
        check_id: the new check's id; the same for the same claim and snapshot.
        corpus_version: the new snapshot the recheck searches.
        claim: the claim to check again, masked like the earlier question.

    Features:
        US-POW-03, US-BEZ-05, F-20, F-39
    """

    model_config = ConfigDict(frozen=True)

    old_check_id: str
    check_id: str
    corpus_version: str
    claim: str


@dataclass(frozen=True, slots=True)
class RecheckDeps:
    """The ports a recheck after a snapshot reads and writes.

    Attributes:
        results: what finished checks answered, for the unanswered claims.
        records: the check records: who asked and whether they are still kept.
        corpus: hybrid search of the new snapshot.
        snapshots: the new and the previous snapshot's manifests.
        inbox: the notification repository.

    Features:
        US-POW-03, F-39
    """

    results: CheckResults
    records: CheckRecordRepository
    corpus: CorpusSearchPort
    snapshots: SnapshotReader
    inbox: NotificationRepository
