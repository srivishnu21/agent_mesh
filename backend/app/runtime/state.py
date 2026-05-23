from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class WorkflowState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    scratchpad: dict
    run_id: str
    workflow_id: str
