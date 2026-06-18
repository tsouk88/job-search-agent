from langsmith import Client
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
import os
import requests


load_dotenv()
llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_retries=10
)
parser = StrOutputParser()
chain = llm|parser

client = Client()

def run_agent(inputs: dict) -> dict:
    response=requests.post("http://localhost:8000/ask" , json={
                        "user_input": inputs["input"],
                        "thread_id": "eval-test"
                    },stream=True)
    return {"output": response.text}


def correctness(run, example) -> dict:
    query = example.inputs["input"]
    results = run.outputs["output"]
    reference = example.outputs["referenceOutput"]
    prompt = f"""You are evaluating a job search agent output.

Query: {query}
Output: {results}
Reference: {reference}

Rules:
- Score 1.0 if ALL jobs in output match the reference criteria
- Score 0.5 if MOST jobs match but some irrelevant ones slipped through
- Score 0.0 if the output is completely wrong or empty when jobs should exist

IMPORTANT: Judge by job title and company name only, not by description quality.
A WordPress company (Automattic, WooCommerce, Pressable) counts as a WordPress job.

Return ONLY a number: 0.0, 0.5, or 1.0"""
    response=chain.invoke(prompt)
    try:
        return {"key": "correctness", "score": float(response.strip())}
    except ValueError:
        return {"key": "correctness", "score": 0}

client.evaluate(run_agent,data="job-search-eval",evaluators=[correctness],experiment_prefix="correctness-test")

                  