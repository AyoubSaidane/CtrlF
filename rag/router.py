from typing import List, Optional, Any
from helper import Answers
from llama_index.core.query_engine import (
    BaseQueryEngine,
    RetrieverQueryEngine,
)
from llama_index.core import PromptTemplate
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import LLM
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    step,
)

class ChooseQueryEngineEvent(Event):
    """Query engine event."""

    answers: Answers
    query_str: str

class SynthesizeAnswersEvent(Event):
    """Synthesize answers event."""

    responses: List[Any]
    query_str: str


class RouterQueryWorkflow(Workflow):
    """Router query workflow."""

    def __init__(
        self,
        query_engines: List[BaseQueryEngine],
        choice_descriptions: List[str],
        router_prompt: PromptTemplate,
        timeout: Optional[float] = 10.0,
        disable_validation: bool = False,
        verbose: bool = False,
        llm: Optional[LLM] = None,
        summarizer: Optional[TreeSummarize] = None,
    ):
        """Constructor"""

        super().__init__(timeout=timeout, disable_validation=disable_validation, verbose=verbose)

        self.query_engines: List[BaseQueryEngine] = query_engines
        self.choice_descriptions: List[str] = choice_descriptions
        self.router_prompt: PromptTemplate = router_prompt
        self.llm: LLM = llm or OpenAI(temperature=0, model="gpt-4o")
        self.summarizer: TreeSummarize = summarizer or TreeSummarize()

    def _get_choice_str(self, choices):
        """String of choices to feed into LLM."""

        choices_str = "\n\n".join([f"{idx+1}. {c}" for idx, c in enumerate(choices)])
        return choices_str

    async def _query(self, query_str: str, choice_idx: int):
        """Query using query engine"""

        query_engine = self.query_engines[choice_idx]
        response = await query_engine.aquery(query_str)
        return response


    @step()
    async def choose_query_engine(self, ev: StartEvent) -> ChooseQueryEngineEvent:
        """Choose query engine."""

        # get query str
        query_str = ev.get("query_str")
        if query_str is None:
            raise ValueError("'query_str' is required.")

        # partially format prompt with number of choices and max outputs
        router_prompt1 = self.router_prompt.partial_format(
            num_choices=len(self.choice_descriptions),
            max_outputs=len(self.choice_descriptions),
        )


        # get choices selected by LLM
        choices_str = self._get_choice_str(self.choice_descriptions)
        output = self.llm.structured_predict(
            Answers,
            router_prompt1,
            context_list=choices_str,
            query_str=query_str
        )

        if self._verbose:
            print(f"Selected choice(s):")
            for answer in output.answers:
                print(f"Choice: {answer.choice}, Reason: {answer.reason}")

        return ChooseQueryEngineEvent(answers=output, query_str=query_str)

    @step()
    async def query_each_engine(self, ev: ChooseQueryEngineEvent) -> SynthesizeAnswersEvent:
        """Query each engine."""

        query_str = ev.query_str
        answers = ev.answers

        # query using corresponding query engine given in Answers list
        responses = []

        for answer in answers.answers:
            choice_idx = answer.choice - 1
            response = await self._query(query_str, choice_idx)
            responses.append(response)
        return SynthesizeAnswersEvent(responses=responses, query_str=query_str)

    @step()
    async def synthesize_response(self, ev: SynthesizeAnswersEvent) -> StopEvent:
        """Synthesizes response."""
        responses = ev.responses
        query_str = ev.query_str

        # Collecter les sources
        sources = []
        for resp in responses:
            if hasattr(resp, 'source_nodes'):
                for node in resp.source_nodes:
                    source = {
                        'file_name': node.metadata.get('file_name', 'Unknown'),
                        'url': node.metadata.get('url', 'Unknown'),
                        'page': node.metadata.get('page_number', 'N/A'),
                        'content': node.text 
                    }
                    sources.append(source)
                    
        # Formater la réponse
        if len(responses) == 1:
            response = responses[0]
        else:
            response_strs = [str(r) for r in responses]
            response = self.summarizer.get_response(
                query_str, 
                response_strs,
                include_metadata=True
            )

        # Formater la réponse finale
        final_response = (
            f"Réponse à votre question : {query_str}\n\n"
            f"<response>\n"
            f"{str(response)}\n"
            f"</response>\n\n"
            f"<source>\n"
            f"{sources}\n"
            f"</source>\n\n"
        )
        
        return StopEvent(result=final_response)
