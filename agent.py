from typing import TypedDict,Annotated
import os
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from dotenv import load_dotenv
from operator import add
import requests

load_dotenv()

class State(TypedDict):
    fetched_jobs : list[dict]
    matched_jobs: Annotated[list[dict], add]
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
        
def evaluate_jobs(state:State):
        llm = init_chat_model(
        model="google_genai:gemini-2.5-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.7,
        max_retries=10
            )
        prompt = f"""You are a personal job evaluator helping the user to find a remote job , the available jobs is in {state["current_job"]} .. An example of a job is :
                    "slug": "remote-executive-assistant-trivium-group-1132766",
        "id": "1132766",
        "epoch": 1780492075,
        "date": "2026-06-03T13:07:55+00:00",
        "company": "Trivium Group",
        "company_logo": "",
        "position": "Executive Assistant",
        "tags": [
        "virtual assistant",
        "exec"
        ],
        "description": "Posted 10:15:23 AM. Location: Remote (US-based preferred â Eastern Time zone required)Employment Type: 1099 Independentâ¦See this and similar jobs on LinkedIn.\u003Cbr/\u003E\u003Cbr/\u003EPlease mention the word **CURE** and tag ROjox when applying to show you read the job post completely (#ROjox). This is a beta feature to avoid spam applicants. Companies can search these words to find applicants that read this and see they're human.",
        "location": "Remote, ",
        "apply_url": ,
        "salary_min": 0,
        "salary_max": 0,
        "logo": "",
        "url": 
        These are the defaults : "position"  related to {state["user_input"]}, "location" needs to be "Remote" and in the "description"look for any of the keywords given by {state["user_input"]} , if user doesnt give all the info needed search only with the given info
        when all these match you send an one and only reply : match if not you reply with : nope"""
        response =llm.invoke(prompt)
        if response.content == "match":
            return {"matched_jobs": [state["current_job"]]}
        return {"matched_jobs": []}
    

def fan_out(state:State):
    return [Send("evaluate" , {**state , "current_job": job}) for job in state["fetched_jobs"]] 


graph = StateGraph(State)
graph.add_node("fetch" , fetch_jobs)
graph.add_node("evaluate" , evaluate_jobs)

graph.add_edge(START, "fetch")
graph.add_conditional_edges("fetch", fan_out)
graph.add_edge("evaluate" , END)
app=graph.compile()
def run_agent(user_input: str):
    result = app.invoke({"user_input": user_input})
    return result["matched_jobs"]



