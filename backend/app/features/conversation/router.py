import uuid

from fastapi import APIRouter, Depends
from redis import Redis

from app.core.redis import get_redis
from app.features.auth.dependencies import get_current_user
from app.features.conversation.schemas import AnswerRequest, BatchAnswerRequest, CreateSessionRequest, TurnResponse
from app.features.conversation.service import ConversationService
from app.features.llm.chain import LLMChain, get_llm_chain

router = APIRouter(prefix="/sessions", tags=["conversation"], dependencies=[Depends(get_current_user)])


def get_conversation_service(
    redis_client: Redis = Depends(get_redis), llm_chain: LLMChain = Depends(get_llm_chain)
) -> ConversationService:
    return ConversationService(redis_client, llm_chain)


@router.post("", response_model=TurnResponse)
def create_session(
    body: CreateSessionRequest = CreateSessionRequest(),
    service: ConversationService = Depends(get_conversation_service),
) -> TurnResponse:
    session_id = str(uuid.uuid4())
    return service.start_session(session_id, body.language)


@router.get("/{session_id}", response_model=TurnResponse)
def get_session(session_id: str, service: ConversationService = Depends(get_conversation_service)) -> TurnResponse:
    return service.get_session_state(session_id)


@router.post("/{session_id}/answer", response_model=TurnResponse)
def submit_answer(
    session_id: str, body: AnswerRequest, service: ConversationService = Depends(get_conversation_service)
) -> TurnResponse:
    return service.submit_answer(session_id, body.field_key, body.text)


@router.post("/{session_id}/answer-batch", response_model=TurnResponse)
def submit_batch_answer(
    session_id: str, body: BatchAnswerRequest, service: ConversationService = Depends(get_conversation_service)
) -> TurnResponse:
    return service.submit_batch_answer(session_id, body.text)


@router.post("/{session_id}/resume", response_model=TurnResponse)
def resume_session(session_id: str, service: ConversationService = Depends(get_conversation_service)) -> TurnResponse:
    return service.resume_session(session_id)
