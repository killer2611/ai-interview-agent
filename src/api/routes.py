import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException


from src.models.api_schemas import InterviewRequest, InterviewResponse
from src.models.candidate import CandidateList

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/candidates", response_model=CandidateList)
async def list_candidates() -> CandidateList:
    """Read-only endpoint returning candidate profiles for demo selection UI."""
    candidates_path = Path(__file__).parent.parent.parent / "candidates.json"
    if not candidates_path.exists():
        raise HTTPException(status_code=404, detail="candidates.json file not found")
    with open(candidates_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data)



def _get_controller_and_store():
    """Lazy getter to obtain singletons from main module."""
    from src.main import curriculum_engine, session_store, llm_provider
    from src.services.interview_controller import InterviewController

    controller = InterviewController(curriculum_engine, llm_provider)
    return controller, session_store


@router.post("/api/interview", response_model=InterviewResponse)
async def interview_endpoint(request: InterviewRequest) -> InterviewResponse:
    """Single endpoint handling full technical interview lifecycle."""
    controller, session_store = _get_controller_and_store()

    # --- INIT REQUEST ---
    if request.candidate is not None:
        logger.info("Init request for session %s (candidate: %s)", request.sessionId, request.candidate.member.name)

        if session_store.exists(request.sessionId):
            raise HTTPException(status_code=409, detail=f"Session already exists: {request.sessionId}")

        state = await controller.initialize_session(request.sessionId, request.candidate)
        session_store.create(state)

        initial_reply = state.conversation_history[0].content if state.conversation_history else "Welcome to your interview."
        return InterviewResponse(reply=initial_reply, done=False)

    # --- TURN REQUEST ---
    elif request.message is not None:
        logger.info("Turn request for session %s", request.sessionId)

        state = session_store.get(request.sessionId)
        if state is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {request.sessionId}")

        if state.is_complete:
            raise HTTPException(status_code=400, detail="Interview is already completed")

        updated_state, reply, done, feedback = await controller.process_turn(state, request.message)
        session_store.update(updated_state)

        return InterviewResponse(reply=reply, done=done, feedback=feedback)

    else:
        raise HTTPException(
            status_code=400,
            detail="Request must contain either 'candidate' (init) or 'message' (turn).",
        )
