import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analysis import AnalysisRunRequest, AnalysisRunResponse
from app.services.analysis_pipeline_service import AnalysisPipelineService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis-pipeline"])


@router.post("/run", response_model=AnalysisRunResponse)
def run_analysis(request: AnalysisRunRequest, db: Session = Depends(get_db)) -> AnalysisRunResponse:
    try:
        return AnalysisPipelineService.response(AnalysisPipelineService.run(db, request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to run analysis pipeline")
        raise HTTPException(status_code=500, detail="Failed to run analysis pipeline") from exc


@router.get("/latest/{symbol}", response_model=AnalysisRunResponse)
def latest_analysis(symbol: str, db: Session = Depends(get_db)) -> AnalysisRunResponse:
    if symbol.upper() != "XAUUSD":
        raise HTTPException(
            status_code=422,
            detail="Analysis execution is restricted to XAUUSD; XAGUSD is confirmation input.",
        )
    run = AnalysisPipelineService.get_latest(db, "XAUUSD")
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return AnalysisPipelineService.response(run)


@router.get("/runs/{run_id}", response_model=AnalysisRunResponse)
def analysis_by_id(run_id: int, db: Session = Depends(get_db)) -> AnalysisRunResponse:
    run = AnalysisPipelineService.get(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return AnalysisPipelineService.response(run)
