from fastapi import FastAPI , UploadFile , Form
from pydantic import BaseModel
from agent import graph
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.postgres import PostgresSaver
from contextlib import asynccontextmanager
import os
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langgraph.types import Command
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
import re
import io
import textwrap

checkpointer_cm = None
agent = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    with PostgresSaver.from_conn_string(os.getenv("DATABASE_URL")) as checkpointer:
        checkpointer.setup()
        agent = graph.compile(checkpointer=checkpointer)
        yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
) 

def run_agent(user_input: str, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"user_input": user_input, "fetched_jobs": []}, 
        config=config
    )
    return result["fetched_jobs"], result.get("memory", [])


class SearchInput(BaseModel):
    user_input: str
    thread_id: str

class FeedbackInput(BaseModel):
    thread_id: str
    feedback: str

class Input(BaseModel):
    user_input: str

class EvaluateInput(BaseModel):
    jobs: str  

llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_retries=10
)
parser = StrOutputParser()
chain = llm|parser

def clean_description(text):
    clean = re.sub(r'<[^>]+>', '', text)
    return textwrap.shorten(clean, width=150, placeholder="...")

@app.post("/ask")
async def askAI(input:SearchInput):
    config = {"configurable": {"thread_id": input.thread_id}}
    state = agent.get_state(config)
    memory = state.values.get("memory", [])
    
    query, _ = run_agent(input.user_input, input.thread_id)
    
    clean_jobs = [{
    "company": j.get("company") or j.get("companyName") or j.get("company_name"),
    "position": j.get("title") or j.get("position", ""),
    "location": j.get("location") or j.get("candidate_required_location") or ", ".join(j.get("locationRestrictions") or []),
    "description": clean_description(j.get("description") or j.get("excerpt", "")),
    "salary": j.get("salary") or f"{j.get('salary_min', '')} - {j.get('salary_max', '')}" or f"{j.get('minSalary', '')} - {j.get('maxSalary', '')}",
    "apply_url": j.get("apply_url") or j.get("url") or j.get("applicationLink")
} for j in query]
    prompt = f"""Filter and present ONLY jobs relevant to: {input.user_input}
    Here are the jobs: {clean_jobs}
    STRICT RULE: Do NOT include any job that involves: {', '.join(memory)}
    If a job title or description contains these words, SKIP it completely.
    if salary is 0 - 0 or empty say not listed
    For each relevant job use this exact format:
    
    - **Position** at **Company** | Location | Salary
      Description
      Apply: url (always leave a space after the url)
    
    Skip jobs that are not related to {input.user_input}
 
    At the end add: "Sources: Some jobs from Remotive.com | RemoteOK.com | Himalayas.app" """
    def generate():
        for chunk in chain.stream(prompt):
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")


@app.post ("/evaluate")
async def evaluaten8n(jobs : EvaluateInput):
    valid_jobs = jobs.jobs
    prompt =f"""You are a personal job evaluator. 
                I am looking for a remote AI/backend engineering job.

                My profile:
                - Self-taught, no formal experience
                - Skills: RAG pipelines, AI agents, LangChain, LangGraph, FastAPI, Next.js, n8n
                - Portfolio: job search agent, restaurant RAG, PDF/HTML extraction API
                - Open to junior/mid roles

                Evaluate these jobs: {valid_jobs}

                For each job, read the description and decide if it fits my profile.
                Keep only the matches. 
                Return them as a simple list: Job Title - Company - one sentence why it fits and then add the link on a new row
                """
    response=chain.invoke(prompt)
    return response

@app.post ("/upload")
async def uploadfile(file: UploadFile, thread_id: str = Form(...)):
    file = await file.read()
    uploadedfile = io.BytesIO(file)
    with pdfplumber.open(uploadedfile) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)

    prompt = f"""You are a job recruiter evaluating candidates , you read their CV through {text} extracting one sentence with all the keywords max 20 words
                    about the candidate"""
    response=chain.invoke(prompt)
    config = {"configurable": {"thread_id": input.thread_id}}
    state = agent.get_state(config)
    memory = state.values.get("memory", [])
    query, _ = run_agent(response, thread_id)
    clean_jobs = [{
        "company": j.get("company") or j.get("companyName") or j.get("company_name"),
        "position": j.get("title") or j.get("position", ""),
        "location": j.get("location") or j.get("candidate_required_location") or ", ".join(j.get("locationRestrictions") or []),
        "description": clean_description(j.get("description") or j.get("excerpt", "")),
        "salary": j.get("salary") or f"{j.get('salary_min', '')} - {j.get('salary_max', '')}" or f"{j.get('minSalary', '')} - {j.get('maxSalary', '')}",
        "apply_url": j.get("apply_url") or j.get("url") or j.get("applicationLink")
            } for j in query]

    prompt = f"""Filter and present ONLY jobs relevant to: {response}
    Here are the jobs: {clean_jobs}
    STRICT RULE: Do NOT include any job that involves: {', '.join(memory)}
    If a job title or description contains these words, SKIP it completely.
    if salary is 0 - 0 or empty say not listed
    For each relevant job use this exact format:
    
    - **Position** at **Company** | Location | Salary
      Description
      Apply: url (always leave a space after the url)
    
    Skip jobs that are not related to {response}
 
    At the end add: "Sources: Some jobs from Remotive.com | RemoteOK.com | Himalayas.app" """
    def generate():
        for chunk in chain.stream(prompt):
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/feedback")
async def human_review(feedback: FeedbackInput):
    config = {"configurable": {"thread_id": feedback.thread_id}}
    extraction_prompt = f"""Extract the job keywords to avoid from this user feedback.
            Return only a comma-separated list of keywords, nothing else.
            IMPORTANT: Only extract what to AVOID, not what the user wants to find.
            Do not include terms like "AI engineer", "python developer" etc.
            Example: "no stack" → "full stack, MERN, MEAN, frontend"
            Feedback: {feedback.feedback}"""
    keywords = chain.invoke(extraction_prompt)
    agent.invoke(Command(resume=keywords), config=config)
    return {"status": "sent to agent"}


           
        


    

