from langsmith import Client
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel , Field, ValidationError
from main import NO_RESULTS, site_of
import os
import requests
import uuid


load_dotenv()

class Output(BaseModel):
    reason : str
    relevant : int
    total : int = Field(ge=1)

class JobOutput(BaseModel):
     reason : str
     relevant : bool
    

llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_retries=10
)

structured_llm = llm.with_structured_output(Output)
eachjob_structured_llm = llm.with_structured_output(JobOutput)


client = Client()
key= os.getenv("EVALS")
apikey=os.getenv("OPENROUTER_API_KEY")

def run_agent(inputs: dict) -> dict:
    response=requests.post("http://localhost:8002/askeval" , json={
                        "user_input": inputs["input"],
                        "thread_id": f"eval-{uuid.uuid4()}" 
                    },  headers = {"x-api-key":key} , timeout=180)
    response.raise_for_status()
    responsecleared=response.json()
    return {"output": responsecleared["md"] , "jobs": responsecleared["jobs"]}


def gemini_full_correctness(run, example) -> dict:
    query = example.inputs["input"]
    jobs = run.outputs["jobs"]
    reference = example.outputs["referenceOutput"]
    if example.outputs.get("empty_ok") and not jobs:
        return {
            "key": "gemini_full_correctness",
            "score": 1.0,
            "comment": "Returned nothing, and the reference accepts nothing. Asserted, not judged.",
        }
    listings = []
    for job in jobs:
        loc = job.get("location", "") or "Location not specified"
        listings.append(f'**- {job.get("position", "")}** at **{job.get("company", "")}** | {loc} | {job.get("salary", "")}  \n {job.get("description", "")} \n Apply: [{site_of(job.get("apply_url", ""))}]({job.get("apply_url", "")})')
    results = "\n\n".join(listings) if listings else NO_RESULTS
    return gemini_grade(query, reference, results, "gemini_full_correctness")


def gemini_grade(query, reference, results, key) -> dict:
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
        return {"key": key, "score": score , "comment": response.reason}
    except ValidationError as e:
        return {"key": key, "comment": f"{e}"}


def askgemini(query , job , criteria):
    instructions =f"""Does this job satisfy the reference criteria or no? When the criteria are silent about a listing, count it as relevant
    Exclusions apply to the role itself. A mention of the company's products, or of who else may apply, does not make the role excluded.
    A role that leans to one side is not excluded by that: a backend-focused full stack role is still full stack.       
        Query: {query}

        Reference criteria:{criteria} 

        Title:{job["position"]}

        Description:{job["description"]}

        Apply_url = {job["apply_url"]}
    """
    
    response=eachjob_structured_llm.invoke(instructions)  
    return response
     
def gemini_listing_correctness (run , example):
    query = example.inputs["input"]
    reference = example.outputs["referenceOutput"]  
    results = run.outputs["jobs"]   
    if example.outputs.get("empty_ok") and not results:
        return {
            "key": "gemini_listing_v3_correctness",
            "score": 1.0,
            "comment": "Returned nothing, and the reference accepts nothing. Asserted, not judged.",
            }
    scores = []
    relevant = 0
    if len(results) == 0:
        return {"key": "gemini_listing_v3_correctness", "score": 0 }
    for job in results:
        score = askgemini(query , job , reference)
        if score.relevant:
            relevant += 1
        scores.append((job["position"], score))
    final_score = relevant / len(scores)
    return {"key": "gemini_listing_v3_correctness", "score": final_score , "comment": str(scores)}
    
def askjev(query , job , criteria):
    instructions = f"""Does this job satisfies the reference criteria or no? When the criteria are silent about a listing, count it as relevant
    {criteria}
    """
    response=requests.post("https://openrouter.ai/api/alpha/decisions" , json={
                            "model": "typesafe/jev-1.13",
                            "state": {"query":query , "job":job["position"] , "description":job["description"] , "Apply_url" : job["apply_url"] } ,
                            "questions": { "relevant": {
                                "type":"noul",
                                "instructions":instructions
                                } 
                            }
                            } , 
                            headers = {"Authorization": "Bearer " + apikey}  , timeout=180)
    response.raise_for_status()
    responsecleared=response.json()
    probability = responsecleared["answers"]["relevant"]["noul"]
    return probability

def jev_correctness(run , example):
    query = example.inputs["input"]
    reference = example.outputs["referenceOutput"]  
    results = run.outputs["jobs"]
    if example.outputs.get("empty_ok") and not results:
            return {
                "key": "jev_correctness",
                "score": 1.0,
                "comment": "Returned nothing, and the reference accepts nothing. Asserted, not judged.",
            }
    scores = []
    skipped =[]
    threshold = 0.5
    relevant = 0
    if len(results) == 0:
        return {"key": "jev_correctness", "score": 0 }
    for job in results:
        score = askjev(query , job , reference)
        if score >= threshold :
            relevant += 1
        else :
            skipped.append((job["position"] , score))
        scores.append((job["position"], score))
    final_score = relevant / len(scores)
    return {"key": "jev_correctness", "score": final_score , "comment": str(scores)}


def asklaya(job ,criteria):
    instructions = "Does this job satisfies the reference criteria or no? When the criteria are silent about a listing, count it as relevant"
    response = requests.post("http://127.0.0.1:8000/v1/systemone", json={
        "model": "multilingual",
        "state": {"job": job["position"],
                  "description": job["description"]},
        "questions": {"relevant": {"type": "noul",
            "instructions": instructions,
            "criteria": {"true": f"the job matches: {criteria}",
                         "false": f"the job does not match: {criteria}"}}}
    }, timeout=60)
    response.raise_for_status()
    responsecleared=response.json()
    probability=responsecleared["answers"]["relevant"]["noul"]
    return probability


def laya_correctness(run, example):
    reference = example.outputs["referenceOutput"]  
    results = run.outputs["jobs"]
    if example.outputs.get("empty_ok") and not results:
                return {
                    "key": "laya_ml_correctness",
                    "score": 1.0,
                    "comment": "Returned nothing, and the reference accepts nothing. Asserted, not judged.",
                }
    scores = []
    skipped =[]
    threshold = 0.5
    relevant = 0
    if len(results) == 0:
        return {"key": "laya_ml_correctness", "score": 0 }
    for job in results:
        score = asklaya(job , reference)
        if score >= threshold :
            relevant += 1
        else :
            skipped.append((job["position"] , score))
        scores.append((job["position"], score))
    final_score = relevant / len(scores)
    return {"key": "laya_ml_correctness", "score": final_score , "comment": str(scores)}





client.evaluate(run_agent,data="job-search-eval" , evaluators=[gemini_full_correctness,jev_correctness,gemini_listing_correctness],experiment_prefix="geminijevfullrun")

                  