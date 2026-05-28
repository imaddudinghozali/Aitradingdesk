from datetime import datetime

from pydantic import BaseModel


class LadderCellResponse(BaseModel):
    label: str
    sub_label: str
    quarter_index: int
    start_utc: datetime
    end_utc: datetime
    is_current: bool


class LadderRowResponse(BaseModel):
    cycle: str
    cells: list[LadderCellResponse]


class QuarterLadderResponse(BaseModel):
    as_of_utc: datetime
    window_start_utc: datetime
    window_end_utc: datetime
    now_ratio: float
    rows: list[LadderRowResponse]
