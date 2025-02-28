from router import RouterQueryWorkflow
from indexer import Indexer
from agent import RouterOutputAgentWorkflow

from llama_index.llms.gemini import Gemini
from llama_index.core import PromptTemplate
from llama_index.core.query_engine import RetrieverQueryEngine


import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from convert import process_input
from fastapi.middleware.cors import CORSMiddleware
from IPython.display import display, Markdown
from dotenv import load_dotenv
load_dotenv()



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

agent = RouterOutputAgentWorkflow(router_query_workflow, verbose=True, timeout=60)

async def process_query(message):
    response = await agent.run(message=message)
    display(Markdown(response))
    return response

async def convert(response):
    return process_input(response)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"]  # Allows all headers
)

class Query(BaseModel):
    message: str


@app.post("/query")
async def query_endpoint(query: Query):
    try:
        # Correctly pass the message string and await directly
        response = await process_query(query.message)
        response = await convert(response)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

if __name__ == "__main__":
    uvicorn.run("processor:app", host="localhost", port=8000, reload=True)


