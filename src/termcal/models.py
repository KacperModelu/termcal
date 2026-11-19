from datetime import datetime
from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime

class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    start_time: NaiveDatetime
    end_time: NaiveDatetime | None = None
    series_id: str | None = Field(default=None, index=True)
