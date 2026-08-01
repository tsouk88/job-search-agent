from langsmith import Client
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel , Field, ValidationError
import os
import requests
import uuid


load_dotenv()

class Output(BaseModel):
    reason : str
    relevant : int
    total : int = Field(ge=1)
    

llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_retries=10
)

structured_llm = llm.with_structured_output(Output)



client = Client()

def run_agent(inputs: dict) -> dict:
    response=requests.post("http://localhost:8002/ask" , json={
                        "user_input": inputs["input"],
                        "thread_id": f"eval-{uuid.uuid4()}"
                    }, timeout=180)
    response.raise_for_status()
    return {"output": response.text}


def correctness(run, example) -> dict:
    query = example.inputs["input"]
    results = run.outputs["output"]
    reference = example.outputs["referenceOutput"]
    prompt = f"""You are evaluating a job search agent output.

Query: {query}
Output: {results}
Reference: {reference}

Rule:
return if the referenceoutput was in line with the jobs in reason
Count how many of the given jobs match the reference criteria , you put this in relevant
total gets the number of the jobs that you get
if you get zero jobs :
    total gets to 1 
    relevant get to 1 if the referenceoutput is alligned or gets to 0 if its not
IMPORTANT: Judge by job title and description content. 
"""
    try:
        response=structured_llm.invoke(prompt)
        score = response.relevant/ response.total   
        return {"key": "correctness", "score": score , "comment": response.reason}
    except ValidationError as e:
        return {"key": "correctness", "comment": f"{e}"}
    
    


client.evaluate(run_agent,data="job-search-eval",evaluators=[correctness],experiment_prefix="correctness-test")

                  