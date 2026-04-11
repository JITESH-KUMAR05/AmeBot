# models
from pydantic import BaseModel, Field
from typing import Optional

class chatRequest(BaseModel):
    """
    message: the user's message
    session_id: the session id
    """
    message: str = Field(..., min_length=1, max_length=1000, description="the user's message")
    session_id: Optional[str] = Field(None, description="the session id")

class chatResponse(BaseModel):
    """
    answer : the bot's reply
    session_id: the session id
    sources : the sources of the answer
    found_in_kb : True if answer came from the knowledge base , False if "I don't know"
    """
    answer : str
    sesstion_id: str
    sources : list[str]
    found_in_kb : bool

class HealthResponse(BaseModel):
    """
    status : the status of the bot
    """
    status : str
    index_loaded:bool
    total_chunks: int