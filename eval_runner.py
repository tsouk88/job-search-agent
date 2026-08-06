from langsmith import Client
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel , Field, ValidationError
from main import NO_RESULTS
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
    if example.outputs.get("empty_ok") and results.startswith(NO_RESULTS):
        return {
            "key": "correctness",
            "score": 1.0,
            "comment": "Returned nothing, and the reference accepts nothing. Asserted, not judged.",
        }
    prompt = f"""You are grading one response from a job search agent.

Query: {query}

Reference criteria:
{reference}

Agent response:
{results}

How to grade:

total = the number of job listings present in the agent response.

relevant = how many of those listings satisfy the reference criteria,
judged on the job title and the description shown, nothing else.

Grade only what is there. A listing that fails the criteria subtracts one
from relevant and nothing more — it never invalidates the other listings.
Never lower the score because a listing you expected is missing.

When the criteria are silent about a listing, count it as relevant. Read
them as written, do not extend them.

If the response contains no listings at all, set total to 1, and set
relevant to 1 if the criteria say an empty answer is acceptable, otherwise 0.

reason = one sentence naming the listings you rejected and why.
"""
    try:
        response=structured_llm.invoke(prompt)
        score = response.relevant/ response.total   
        return {"key": "correctness", "score": score , "comment": response.reason}
    except ValidationError as e:
        return {"key": "correctness", "comment": f"{e}"}
    
    


client.evaluate(run_agent,data="job-search-eval",evaluators=[correctness],experiment_prefix="correctness-test")

                  