from typing import List, Optional, Any
from llama_index.core.bridge.pydantic import BaseModel
from llama_index.core.query_engine import (
    BaseQueryEngine
)
from llama_index.core import PromptTemplate
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import LLM
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    step,
)

class Answer(BaseModel):
    """Answer model."""

    choice: int
    reason: str

class Answers(BaseModel):
    """List of answers model."""

    answers: List[Answer]

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
        self.llm: LLM = llm or Gemini(temperature=0, model="gemini-2.0-flash-001")
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
                    print("this is metadata",node.metadata)
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

async def main():
    from indexer import Indexer
    from llama_index.llms.gemini import Gemini
    from llama_index.core.query_engine import RetrieverQueryEngine
    try:
        indexer = Indexer()
        index = indexer.retrieve_index()
        llm = Gemini(model = "models/gemini-2.0-flash")

        doc_retriever = index.as_retriever(
            retrieval_mode="files_via_content", 
            files_top_k=1,
            include_metadata=True
        )
        query_engine_doc = RetrieverQueryEngine.from_args(
            doc_retriever, 
            llm=llm, 
            response_mode="tree_summarize",
            response_synthesizer_kwargs={
                "text_template": (
                    "Document complet (pages {metadata[page_number]}):\n"
                    "```\n"
                    "{text}\n"
                    "```\n\n"
                ),
                "include_metadata": True
            }
        )

        chunk_retriever = index.as_retriever(
            retrieval_mode="chunks", 
            rerank_top_n=10,
            include_metadata=True
        )
        query_engine_chunk = RetrieverQueryEngine.from_args(
            chunk_retriever, 
            llm=llm, 
            response_mode="tree_summarize",
            response_synthesizer_kwargs={
                "text_template": (
                    "Page {metadata[page_number]}:\n"
                    "```\n"
                    "{text}\n"
                    "```\n\n"
                ),
                "include_metadata": True
            }
        )

        # tells LLM to select choices given a list
        ROUTER_PROMPT = PromptTemplate(
            "Some choices are given below. It is provided in a numbered list (1 to"
            " {num_choices}), where each item in the list corresponds to a"
            " summary.\n---------------------\n{context_list}\n---------------------\nUsing"
            " only the choices above and not prior knowledge, return the top choices"
            " (no more than {max_outputs}, but only select what is needed) that are"
            " most relevant to the question: '{query_str}'\n"
        )


        DOC_METADATA_EXTRA_STR = """\
        Each document represents a PPT presentation produced by a consulting group

        """

        TOOL_DOC_DESC = f"""\
        Synthesizes an answer to your question by feeding in an entire relevant document as context. Best used for higher-level summarization options.
        Do NOT use if answer can be found in a specific chunk of a given document. Use the chunk_query_engine instead for that purpose.

        Below we give details on the format of each document:
        {DOC_METADATA_EXTRA_STR}
        """

        TOOL_CHUNK_DESC = f"""\
        Synthesizes an answer to your question by feeding in a relevant chunk as context. Best used for questions that are more pointed in nature.
        Do NOT use if the question asks seems to require a general summary of any given document. Use the doc_query_engine instead for that purpose.

        Below we give details on the format of each document:
        {DOC_METADATA_EXTRA_STR}
        """

        router_query_workflow = RouterQueryWorkflow(
            query_engines=[query_engine_doc, query_engine_chunk],
            choice_descriptions=[TOOL_DOC_DESC, TOOL_CHUNK_DESC],
            verbose=True,
            llm=llm,
            router_prompt=ROUTER_PROMPT,
            timeout=60
        )
        user_message = "tell me about the media in NYC in 2012"
        
        rag_response = await router_query_workflow.run(query_str=user_message)
        print(rag_response)


    except Exception as e:
        print(f"Error occurred: {str(e)}")
    


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())