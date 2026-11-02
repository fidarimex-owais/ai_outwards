from fastapi import APIRouter, Depends
from pymongo.database import Database
from redis import Redis

from app.core.mongodb import get_db
from app.core.redis import get_redis
from app.features.auth.dependencies import get_current_user
from app.features.conversation.schemas import TurnResponse
from app.features.llm.chain import LLMChain, get_llm_chain
from app.features.submissions.schemas import CorrectionRequest, SubmissionOut
from app.features.submissions.service import SubmissionService

router = APIRouter(prefix="/sessions", tags=["submissions"], dependencies=[Depends(get_current_user)])


def get_submission_service(
    redis_client: Redis = Depends(get_redis),
    db: Database = Depends(get_db),
    llm_chain: LLMChain = Depends(get_llm_chain),
) -> SubmissionService:
    return SubmissionService(redis_client, db, llm_chain)


@router.post("/{session_id}/confirm", response_model=SubmissionOut)
def confirm_session(
    session_id: str, service: SubmissionService = Depends(get_submission_service)
) -> SubmissionOut:
    return service.confirm(session_id)


@router.patch("/{session_id}/fields/{field_key}", response_model=TurnResponse)
def correct_field(
    session_id: str,
    field_key: str,
    body: CorrectionRequest,
    service: SubmissionService = Depends(get_submission_service),
) -> TurnResponse:
    return service.correct_field(session_id, field_key, body.text)
