from pydantic import BaseModel
from typing import Optional, Literal

from pydantic import BaseModel
from typing import List
from datetime import datetime

# Message
class ResponseHTTPChat(BaseModel):
    id: str
    text: str
    
class RequestHTTPChat(BaseModel):
    message_id: str
    conversation_id: str
    conversation_name: str
    query: str
    flag_modifier: Optional[bool] = False
    model_name: Optional[Literal["gpt-4o", "o1", "o1-mini"]] = None
    search_tool: Optional[bool] = None

# Vote
class RequestHTTPVote(BaseModel):
    id: str
    thread_id: str
    rate: Literal[None,0,1,2]

class ResponseHTTPVote(BaseModel):
    id: str
    text: str
    state: Literal[None,0,1,2]
    
#Sessions
class ResponseHTTPSessions(BaseModel):
    sessions:list
    
# One Session
class RequestHTTPOneSession(BaseModel):
    conversation_id: str

class Message(BaseModel):
    id: str 
    role: str 
    content: str 
    created_at: datetime
    rate: Optional[Literal[None,0,1,2]] = None
    files: Optional[List[str]] = None

class ResponseHTTPOneSession(BaseModel):
    conversation_id: str
    conversation_name:str
    messages: list[Message]

class ResponseHTTPDelete(BaseModel):
    message: str
    deleted_count: int