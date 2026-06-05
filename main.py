from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent
import os
from langchain.chat_models import init_chat_model
from fastapi.middleware.cors import CORSMiddleware

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

llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7,
    max_retries=10
)


@app.post("/ask")
async def askAI(input:Input):
    query = run_agent(input.user_input)
    prompt = f"""Present ONLY these exact jobs to the user, do not invent or add any other jobs. 
    Here are the jobs: {query}
    Present each job clearly with: company, position, location, apply_url."""
    response = llm.invoke(prompt)
    return {"results": response.content}
    

