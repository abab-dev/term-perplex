import typer
import re
from typing import List, Any, Optional

from rich import print
from rich.prompt import Prompt

import langroid as lr
import langroid.language_models as lm
from langroid.agent.tools.orchestration import ForwardTool
from langroid.agent.tool_message import ToolMessage
from langroid.agent.chat_agent import ChatAgent, ChatDocument
from langroid.agent.special.doc_chat_agent import (
    DocChatAgent,
    DocChatAgentConfig,
)
from langroid.embedding_models.models import GeminiEmbeddingsConfig
from langroid.parsing.web_search import duckduckgo_search
from langroid.agent.task import Task
from langroid.utils.constants import NO_ANSWER
from langroid.utils.configuration import set_global, Settings
from fire import Fire
from langroid.parsing.url_loader import TrafilaturaConfig, FirecrawlConfig
embed_cfg = GeminiEmbeddingsConfig(
    model_type="gemini",
)


class RelevantExtractsTool(ToolMessage):
    request = "relevant_extracts"
    purpose = "Get docs/extracts relevant to the <query>"
    query: str

    @classmethod
    def examples(cls) -> List["ToolMessage"]:
        return [
            cls(query="when was the Mistral LLM released?"),
        ]

    @classmethod
    def instructions(cls) -> str:
        return """
        IMPORTANT: You must include an ACTUAL query in the `query` field,
        """


class RelevantSearchExtractsTool(ToolMessage):
    request = "relevant_search_extracts"
    purpose = "Get docs/extracts relevant to the <query> from a web search"
    query: str
    num_results: int = 3

    @classmethod
    def examples(cls) -> List["ToolMessage"]:
        return [
            cls(
                query="when was the Mistral LLM released?",
                num_results=3,
            ),
        ]

    @classmethod
    def instructions(cls) -> str:
        return """
        IMPORTANT: You must include an ACTUAL query in the `query` field,
        """


class SearchDocChatAgent(DocChatAgent):
    tried_vecdb: bool = False
    crawler: Optional[str] = None

    def __init__(self, config: DocChatAgentConfig, crawler: Optional[str] = None):
        super().__init__(config)
        self.tried_vecdb = False
        self.crawler = crawler
        self.update_crawler_config(crawler)

    def update_crawler_config(self, crawler: Optional[str]):
        """Updates the crawler config based on the crawler argument."""
        if crawler == "firecrawl":
            self.config.crawler_config = FirecrawlConfig()
        elif crawler == "trafilatura" or crawler is None:
            self.config.crawler_config = TrafilaturaConfig()
        else:
            raise ValueError(
                f"Unsupported crawler {crawler}. Options are: 'trafilatura', 'firecrawl'"
            )

    def llm_response(
        self,
        message: None | str | ChatDocument = None,
    ) -> ChatDocument | None:
        return ChatAgent.llm_response(self, message)

    def handle_message_fallback(self, msg: str | ChatDocument) -> Any:
        if isinstance(msg, ChatDocument) and msg.metadata.sender == lr.Entity.LLM:
            return ForwardTool(agent="user")

    def relevant_extracts(self, msg: RelevantExtractsTool) -> str:
        """Get docs/extracts relevant to the query, from vecdb"""
        self.tried_vecdb = True
        query = msg.query
        _, extracts = self.get_relevant_extracts(query)
        if len(extracts) == 0:
            return """
            No extracts found! You can try doing a web search with the
            `relevant_search_extracts` tool/function-call.
            """
        return "\n".join(str(e) for e in extracts)

    def relevant_search_extracts(self, msg: RelevantSearchExtractsTool) -> str:
        """Get docs/extracts relevant to the query, from a web search"""
        if not self.tried_vecdb and len(self.original_docs) > 0:
            return "Please try the `relevant_extracts` tool, before using this tool"
        self.tried_vecdb = False
        query = msg.query
        num_results = msg.num_results
        results = duckduckgo_search(query, num_results)
        links = [r.link for r in results]
        self.config.doc_paths = links
        self.ingest()
        _, extracts = self.get_relevant_extracts(query)
        return "\n".join(str(e) for e in extracts)


def cli():
    Fire(main)


app = typer.Typer()


@app.command()
def main(
    debug: bool = False,
    nocache: bool = False,
    model: str = "",
    fn_api: bool = True,
    crawler: Optional[str] = typer.Option(
        None,
        "--crawler",
        "-c",
        help="Specify a crawler to use (trafilatura, firecrawl)",
    ),
) -> None:
    """
    Main function to run the chatbot.

    Args:
        debug (bool): Enable debug mode.
        nocache (bool): Disable caching.
        model (str): Specify the LLM model to use.
        fn_api (bool): Use OpenAI functions API instead of tools.
        crawler (str): Specify the crawler to use for web search.
    """

    set_global(
        Settings(
            debug=debug,
            cache=not nocache,
        )
    )

    print(
        """
        [blue]Welcome to the Internet Search chatbot!
        I will try to answer your questions, relying on (full content of links from) 
        Duckduckgo (DDG) Search when needed.
        
        Enter x or q to quit, or ? for evidence
        """
    )

    system_msg = Prompt.ask(
        """
    [blue] Tell me who I am (give me a role) by completing this sentence: 
    You are...
    [or hit enter for default]
    [blue] Human
    """,
        default="a helpful assistant.",
    )
    system_msg = re.sub("you are", "", system_msg, flags=re.IGNORECASE)

    llm_config = lm.OpenAIGPTConfig(
        chat_model="gemini/gemini-2.0-flash",
        chat_context_length=8000,
    )

    config = DocChatAgentConfig(
        use_functions_api=fn_api,
        use_tools=not fn_api,
        llm=llm_config,
        vecdb=lr.vector_store.ChromaDBConfig(
            embedding=embed_cfg,
        ),
        system_message=f"""
        {system_msg} You will try your best to answer my questions,
        in this order of preference:
        1. If you can answer from your own knowledge, simply return the answer
        2. Otherwise, ask me for some relevant text, and I will send you. Use the 
            `relevant_extracts` tool/function-call for this purpose. Once you receive 
            the text, you can use it to answer my question. 
            If I say {NO_ANSWER}, it means I found no relevant docs, and you can try 
            the next step, using a web search.
        3. If you are still unable to answer, you can use the `relevant_search_extracts`
           tool/function-call to get some text from a web search. Once you receive the
           text, you can use it to answer my question.
        5. If you still can't answer, simply say {NO_ANSWER} 
        
        Remember to always FIRST try `relevant_extracts` to see if there are already 
        any relevant docs, before trying web-search with `relevant_search_extracts`.
        
        Be very concise in your responses, use no more than 1-2 sentences.
        When you answer based on provided documents, be sure to show me 
        the SOURCE(s) and EXTRACT(s), for example:
        
        SOURCE: https://www.wikihow.com/Be-a-Good-Assistant-Manager
        EXTRACT: Be a Good Assistant ... requires good leadership skills.
        
        For the EXTRACT, ONLY show up to first 3 words, and last 3 words.
        """,
    )

    agent = SearchDocChatAgent(config, crawler=crawler)
    agent.enable_message(RelevantExtractsTool)
    agent.enable_message(RelevantSearchExtractsTool)
    collection_name = Prompt.ask(
        "Name a collection to use",
        default="docqa-chat-search",
    )
    replace = (
        Prompt.ask(
            "Would you like to replace (i.e. erase) this collection?",
            choices=["y", "n"],
            default="n",
        )
        == "y"
    )

    print(f"[red]Using {collection_name}")

    agent.vecdb.set_collection(collection_name, replace=replace)

    task = Task(agent, interactive=False)
    task.run(
        "Can you help me answer some questions, possibly using web search and crawling?"
    )


if __name__ == "__main__":
    app()
