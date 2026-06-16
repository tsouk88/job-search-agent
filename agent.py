from typing import TypedDict,Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send , interrupt
from dotenv import load_dotenv
from operator import add
import requests



load_dotenv()


class State(TypedDict):
    fetched_jobs: Annotated[list[dict], add]
    current_job: dict
    user_input: str = ""
    memory: Annotated[list[str], add]



def search(state: State):
    return {}
   
def fetch_jobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        response= requests.get("https://remoteok.com/api")
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = [job for job in data if 
        any(keyword.lower() in job.get("position", "").lower() or 
        keyword.lower() in job.get("description", "").lower() 
        for keyword in state["user_input"].split())][:10]
        return  {"fetched_jobs":fetched_jobs}

def fetch_sjobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        response= requests.get(f"https://himalayas.app/jobs/api/search?q={state["user_input"]}&worldwide=true&sort=recent")
        if response.status_code == 429:
            return {"fetched_jobs": []}
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = data["jobs"][:10]
        
        return  {"fetched_jobs":fetched_jobs}

def fetch_tjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    response= requests.get(f"https://remotive.com/api/remote-jobs?search={state['user_input']}&limit=10")
    if response.status_code == 429:
        return {"fetched_jobs": []}
    data = response.json() 
    jobs = data["jobs"]
    locationmatch = ["worldwide" , "europe" , "anywhere"]
    # Limit to 10 jobs for cost control — remove [:10] to search all jobs
    fetched_jobs = [job for job in jobs if
        any(loc in job.get("candidate_required_location", "").lower()
            for loc in locationmatch)][:10]
    return  {"fetched_jobs":fetched_jobs}

def collect_results(state: State):
    seen = set()
    unique_jobs = []
    for job in state["fetched_jobs"]:
        key = job.get("apply_url") or job.get("url")
        if key not in seen:
            seen.add(key)
            unique_jobs.append(job)
    return {"fetched_jobs": unique_jobs}

def human_review(state: State):
    feedback = interrupt("Review jobs and tell me what to skip (e.g. 'no MERN, no full stack')")
    return {"memory": [feedback]}

def should_continue(state: State):
    last_feedback = state["memory"][-1] if state["memory"] else ""
    if last_feedback == "done":
        return END
    return "search"
        

def fan_out(state:State):
     return [
        Send("fetch_jobs", state),   
        Send("fetch_sjobs", state),  
        Send("fetch_tjobs", state),  
    ]


graph = StateGraph(State)
graph.add_node("search", search)
graph.add_node("fetch_jobs" , fetch_jobs)
graph.add_node("fetch_sjobs" , fetch_sjobs)
graph.add_node("fetch_tjobs" , fetch_tjobs)
graph.add_node("collect_results", collect_results)
graph.add_node("human_review" , human_review)


graph.add_conditional_edges(START, fan_out)
graph.add_edge("fetch_jobs", "collect_results")
graph.add_edge("fetch_sjobs", "collect_results")
graph.add_edge("fetch_tjobs", "collect_results")
graph.add_edge("collect_results", "human_review")
graph.add_conditional_edges("human_review", should_continue, {"search": "search", END: END})
graph.add_conditional_edges("search", fan_out)








