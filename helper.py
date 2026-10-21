from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field
from urllib.parse import urlparse
import textwrap

class CVKeywords(BaseModel):
    keywords: list[str] = Field(
        description=(
            "Search keywords for this candidate's job hunt, most important first. "
            "Start with the role title (e.g. 'backend developer', 'data analyst', "
            "'graphic designer', 'accountant'), then the core skills or tools "
            "(e.g. 'python', 'figma', 'excel'). "
            "One or two words each, lowercase. No filler words like 'and', 'with', "
            "'skilled', 'experience', 'years'."
        )
    )

def llmchain(given_api_key: str | None , for_upload: bool = False) -> Runnable:
    llm = init_chat_model(
            model="google_genai:gemini-2.5-flash",
            api_key=given_api_key,
            temperature=0.1,
            max_retries=10
        )
    parser = StrOutputParser()
    if for_upload :
        wsllm=llm.with_structured_output(CVKeywords)
        return wsllm
    chain = llm|parser
    return chain

def run_agent(agent: Runnable ,user_input: str, thread_id: str, country: str = "" , metadata: dict | None=None):
    if metadata is None :
        metadata={}
    config = {"configurable": {"thread_id": thread_id} , "metadata": metadata } 
    result = agent.invoke(
        {"user_input": user_input, "country": country, "fetched_jobs": []}, 
        config=config
    )
    return result["clean_jobs"], result.get("memory", []) , result.get("last_fetch_time", "")

SOURCES = "Sources: Some jobs from Remotive.com | RemoteOK.com | Himalayas.app | Jobicy.com | jobs.workable.com"

NO_RESULTS = ("No jobs matched your search and active filters.\n\n"
              "Try a different search, or say \"reset filters\" to clear what you excluded.")

def active_filters_line(memory: list | None, country: str = "") -> str:
    """Footer: where these listings were searched, and what was excluded.

    The country belongs here because feedback re-filters the last search rather
    than running a new one - it is meant to be instant, not five more API calls.
    So changing the dropdown and asking to exclude something shows the previous
    country's listings, and this line is what tells the reader so."""
    parts = [f"Showing: {country.replace('-', ' ').title() if country else 'Worldwide'}"]
    seen = []
    for entry in memory or []:
        for keyword in entry.split(","):
            keyword = keyword.strip()
            if keyword and keyword.lower() not in [s.lower() for s in seen]:
                seen.append(keyword)
    if seen:
        parts.append(f"Active filters: {', '.join(seen)} — say \"reset filters\" to clear")
    return "\n\n" + " · ".join(parts)

# The boards spell their own names, and the domain does not always carry them:
# jobs.workable.com reads as "Jobs" and remoteOK.com as "Remoteok".
SITE_NAMES = {
    "workable": "Workable",
    "remoteok": "RemoteOK",
    "himalayas": "Himalayas",
    "jobicy": "Jobicy",
    "remotive": "Remotive",
}


def site_of(apply_url: str) -> str:
    """The board a listing came from, named the way the board names itself."""
    labels = urlparse(apply_url).netloc.lower().split(".")
    domain = labels[-2] if len(labels) > 1 else (labels[0] if labels else "")
    return SITE_NAMES.get(domain, domain.capitalize())


def format_jobs_markdown(jobs: list, memory: list | None = None, country: str = "") -> str:
    filters = active_filters_line(memory, country)
    if not jobs:
        return NO_RESULTS + filters
    form_jobs = []
    for job in jobs:
        site_name = site_of(job.get("apply_url", ""))
        loc = job.get("location" , "")
        description = job.get("description" , "")
        if not loc:
            loc = "Location not specified"
        formatted = f'**- {job.get("position", "")}** at **{job.get("company", "")}** | {loc} | {job.get("salary" , "")}  \n {textwrap.shorten(description, width=150, placeholder="...")} \n Apply: [{site_name}]({job.get("apply_url", "")})'
        form_jobs.append(formatted)
    format_str = "\n\n".join(form_jobs)
    return f"{format_str}\n\n{SOURCES}{filters}"
