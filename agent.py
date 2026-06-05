from typing import TypedDict,Annotated
import os
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from dotenv import load_dotenv
from operator import add
import requests
import re

load_dotenv()

class State(TypedDict):
    fetched_jobs : list[dict]
    matched_jobs: Annotated[list[dict], add]
    current_job: dict
    user_input: str

def clean_description(text):
    return re.sub(r'<[^>]+>', '', text)[:500]
   
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
        job_summary = {
                    "position": state["current_job"].get("position"),
                    "location": state["current_job"].get("location"),
                    "description": clean_description(state["current_job"].get("description", ""))
                }    
        prompt = f"""Evaluate this job for a remote position.
                        Job: {job_summary}
                        Requirements: position related to {state["user_input"]}, description must mention any of: {state["user_input"]}
                        Reply with only: match or nope"""
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



