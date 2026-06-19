from typing import TypedDict,Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send , interrupt
from operator import add
import urllib.parse
import requests




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
        first_keyword = state['user_input'].split()[0].lower()
        query = urllib.parse.quote(first_keyword)
        response = requests.get(
                f"https://remoteok.com/api?tags={query}",
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0"}
            )
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = [job for job in data 
        if isinstance(job, dict) and
        any(keyword.lower() in [t.lower() for t in job.get("tags", [])]
        or keyword.lower() in job.get("position", "").lower()
        for keyword in state["user_input"].split())][:10]
        for job in fetched_jobs:
            job["description"] = job.get("description", "")[:100]
        return {"fetched_jobs": fetched_jobs}
        
def fetch_sjobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        query = urllib.parse.quote(state['user_input'])
        response= requests.get(f"https://himalayas.app/jobs/api/search?q={query}&worldwide=true&sort=recent")
        if response.status_code == 429:
            return {"fetched_jobs": []}
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = data["jobs"][:10]  
        for job in fetched_jobs:
            job["description"] = job.get("description", "")[:100]
        return {"fetched_jobs": fetched_jobs}

def fetch_tjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    query = urllib.parse.quote(state['user_input'])
    response= requests.get(f"https://remotive.com/api/remote-jobs?search={query}")
    if response.status_code == 429:
        return {"fetched_jobs": []}
    data = response.json() 
    fetched_jobs = data["jobs"][:10]  
    for job in fetched_jobs:
        job["description"] = job.get("description", "")[:100]
    return {"fetched_jobs": fetched_jobs}

#def fetch_fijobs(state:State):
#    if not state.get("user_input"):
#        return {"fetched_jobs": []}
#    response= requests.get("https://arbeitnow.com/api/job-board-api")
#    data = response.json()
#    fetched_jobs = [job for job in data["data"] 
#    if job.get("remote") == True
#    and job.get("location", "").lower() in ["", "remote", "worldwide"]
#    and any(keyword.lower() in job.get("title", "").lower() or 
#            keyword.lower() in job.get("description", "").lower()
#            for keyword in state["user_input"].split())][:10]
#    for job in fetched_jobs:
#        job["description"] = job.get("description", "")[:100]
#    return {"fetched_jobs": fetched_jobs}

def fetch_fjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    query = urllib.parse.quote(state['user_input'])
    response= requests.get(f"https://jobicy.com/api/v2/remote-jobs?tag={query}")
    if response.status_code == 429:
        return {"fetched_jobs": []}
    data = response.json() 
    fetched_jobs = data["jobs"][:10]
    for job in fetched_jobs:
        job["jobDescription"] = job.get("jobDescription", "")[:100]
    return {"fetched_jobs": fetched_jobs}

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
        Send("fetch_fjobs", state)
       # Send("fetch_fijobs", state)    
    ]


graph = StateGraph(State)
graph.add_node("search", search)
graph.add_node("fetch_jobs" , fetch_jobs)
graph.add_node("fetch_sjobs" , fetch_sjobs)
graph.add_node("fetch_tjobs" , fetch_tjobs)
graph.add_node("fetch_fjobs", fetch_fjobs)
#graph.add_node("fetch_fijobs", fetch_fijobs)
graph.add_node("collect_results", collect_results)
graph.add_node("human_review" , human_review)


graph.add_conditional_edges(START, fan_out)
graph.add_edge("fetch_jobs", "collect_results")
graph.add_edge("fetch_sjobs", "collect_results")
graph.add_edge("fetch_tjobs", "collect_results")
graph.add_edge("fetch_fjobs", "collect_results")
#graph.add_edge("fetch_fijobs", "collect_results")
graph.add_edge("collect_results", "human_review")
graph.add_conditional_edges("human_review", should_continue, {"search": "search", END: END})
graph.add_conditional_edges("search", fan_out)








