from typing import TypedDict,Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from dotenv import load_dotenv
from operator import add
import requests


load_dotenv()

class State(TypedDict):
    fetched_jobs : Annotated[list[dict], add]
    current_job: dict
    user_input: str



   
def fetch_jobs(state:State):
        response= requests.get("https://remoteok.com/api")
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = [job for job in data if 
        any(keyword.lower() in job.get("position", "").lower() or 
        keyword.lower() in job.get("description", "").lower() 
        for keyword in state["user_input"].split())][:10]
        return  {"fetched_jobs":fetched_jobs}

def fetch_sjobs(state:State):
        response= requests.get(f"https://himalayas.app/jobs/api/search?q={state["user_input"]}&worldwide=true&sort=recent")
        if response.status_code == 429:
            return {"fetched_jobs": []}
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = data["jobs"][:10]
        return  {"fetched_jobs":fetched_jobs}

def fetch_tjobs(state:State):
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

def collect_results(state:State):                 
  return {}
        

def fan_out(state:State):
     return [
        Send("fetch_jobs", state),   
        Send("fetch_sjobs", state),  
        Send("fetch_tjobs", state),  
    ]


graph = StateGraph(State)
graph.add_node("fetch_jobs" , fetch_jobs)
graph.add_node("fetch_sjobs" , fetch_sjobs)
graph.add_node("fetch_tjobs" , fetch_tjobs)
graph.add_node("collect_results", collect_results)

graph.add_conditional_edges(START, fan_out)
graph.add_edge("fetch_jobs", "collect_results")
graph.add_edge("fetch_sjobs", "collect_results")
graph.add_edge("fetch_tjobs", "collect_results")
graph.add_edge("collect_results", END)

app=graph.compile()
def run_agent(user_input: str):
    result = app.invoke({"user_input": user_input})
    return result["fetched_jobs"]



