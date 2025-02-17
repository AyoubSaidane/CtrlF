from typing import Dict, List
from typing import List, Optional, Any
from llama_index.core.tools import BaseTool
from llama_index.core.llms import ChatMessage
from llama_index.core.llms.llm import ToolSelection
from llama_index.core.workflow import Context, Workflow
from llama_index.core.base.response.schema import Response
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import LLM
from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    step,
)


class InputEvent(Event):
    """Input event."""

class GatherToolsEvent(Event):
    """Gather Tools Event"""

    tool_calls: Any

class ToolCallEvent(Event):
    """Tool Call event"""

    tool_call: ToolSelection

class ToolCallEventResult(Event):
    """Tool call event result."""

    msg: ChatMessage


class RouterOutputAgentWorkflow(Workflow):
    """Custom router output agent workflow."""

    def __init__(self,
        rag_workflow: Workflow,
        timeout: Optional[float] = 10.0,
        disable_validation: bool = False,
        verbose: bool = False,
        llm: Optional[LLM] = None,
        chat_history: Optional[List[ChatMessage]] = None,
    ):
        """Constructor."""

        super().__init__(timeout=timeout, disable_validation=disable_validation, verbose=verbose)

        self.rag_workflow = rag_workflow

        def query_workflow(query_str: str) -> Response:
            """Queries 10k reports for a given year."""
            return self.rag_workflow.run(query_str=query_str)

        self.rag_workflow_tool = FunctionTool.from_defaults(query_workflow)

        self.llm: LLM = llm or OpenAI(temperature=0, model="gpt-4o")
        self.chat_history: List[ChatMessage] = chat_history or []


    def reset(self) -> None:
        """Resets Chat History"""

        self.chat_history = []

    @step()
    async def prepare_chat(self, ev: StartEvent) -> InputEvent:
        message = ev.get("message")
        if message is None:
            raise ValueError("'message' field is required.")

        # add msg to chat history
        chat_history = self.chat_history
        chat_history.append(ChatMessage(role="user", content=message))
        return InputEvent()

    @step()
    async def chat(self, ev: InputEvent) -> GatherToolsEvent | StopEvent:
        """Appends msg to chat history, then gets tool calls."""

        # Put msg into LLM with tools included
        chat_res = await self.llm.achat_with_tools(
            [self.rag_workflow_tool],
            chat_history=self.chat_history,
            verbose=self._verbose,
            allow_parallel_tool_calls=True
        )
        tool_calls = self.llm.get_tool_calls_from_response(chat_res, error_on_no_tool_call=False)

        ai_message = chat_res.message
        self.chat_history.append(ai_message)
        if self._verbose:
            print(f"Chat message: {ai_message.content}")

        # If no tool calls, directly run RAG workflow with the user's last message
        if not tool_calls:
            last_user_message = self.chat_history[-2].content  # Get the last user message
            rag_response = await self.rag_workflow.run(query_str=last_user_message)
            return StopEvent(result=f"{ai_message.content}\n\nRAG Response: {str(rag_response)}")

        return GatherToolsEvent(tool_calls=tool_calls)

    @step(pass_context=True)
    async def dispatch_calls(self, ctx: Context, ev: GatherToolsEvent) -> ToolCallEvent:
        """Dispatches calls."""

        tool_calls = ev.tool_calls
        await ctx.set("num_tool_calls", len(tool_calls))

        # trigger tool call events
        for tool_call in tool_calls:
            ctx.send_event(ToolCallEvent(tool_call=tool_call))

        return None

    @step()
    async def call_tool(self, ev: ToolCallEvent) -> ToolCallEventResult:
        """Calls tool."""

        tool_call = ev.tool_call

        # get tool ID and function call
        id_ = tool_call.tool_id

        if self._verbose:
            print(f"Calling function {tool_call.tool_name} with msg {tool_call.tool_kwargs}")

        # directly run workflow, don't call tools
        output = await self.rag_workflow.run(**tool_call.tool_kwargs)
        msg = ChatMessage(
            name=tool_call.tool_name,
            content=str(output),
            role="tool",
            additional_kwargs={
                "tool_call_id": id_,
                "name": tool_call.tool_name
            }
        )

        return ToolCallEventResult(msg=msg)

    @step(pass_context=True)
    async def gather(self, ctx: Context, ev: ToolCallEventResult) -> StopEvent | None:
        """Gathers tool calls."""
        # wait for all tool call events to finish.
        tool_events = ctx.collect_events(ev, [ToolCallEventResult] * await ctx.get("num_tool_calls"))
        if not tool_events:
            return None

        for tool_event in tool_events:
            # append tool call chat messages to history
            self.chat_history.append(tool_event.msg)

        # # after all tool calls finish, pass input event back, restart agent loop
        return InputEvent()
