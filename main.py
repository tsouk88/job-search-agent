from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent
from fastapi.responses import StreamingResponse
import os
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile
import pdfplumber
import re
import io
import textwrap

app=FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)   

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
async def askAI(input:Input):
    query = run_agent(input.user_input)
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
    if salary is 0 - 0 or empty say not listed
    For each relevant job use this exact format:
    
    - **Position** at **Company** | Location | Salary
      Description
      Apply: url (always leave a space after the url)
    
    Skip jobs that are not related to {input.user_input}
 
    At the end add: "Sources: Some jobs from Remotive.com | RemoteOK.com | Himalayas.app" """
    def generate():
        for chunk in llm.stream(prompt):
            yield chunk.content
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
async def uploadfile(file:UploadFile):
    file = await file.read()
    uploadedfile = io.BytesIO(file)
    with pdfplumber.open(uploadedfile) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)

    prompt = f"""You are a job recruiter evaluating candidates , you read their CV through {text} extracting one sentence with all the keywords max 20 words
                    about the candidate"""
    response=chain.invoke(prompt)
    query = run_agent(response)
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
    if salary is 0 - 0 or empty say not listed
    For each relevant job use this exact format:
    
    - **Position** at **Company** | Location | Salary
      Description
      Apply: url (always leave a space after the url)
    
    Skip jobs that are not related to {response}
 
    At the end add: "Sources: Some jobs from Remotive.com | RemoteOK.com | Himalayas.app" """
    def generate():
        for chunk in llm.stream(prompt):
            yield chunk.content
    return StreamingResponse(generate(), media_type="text/plain")


           
        


    

