from dotenv import load_dotenv
import os
from helper import llmchain , run_agent, format_jobs_markdown
from agent import normalize_jobs , filter_jobs , graph
from celery import Celery
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()
REDIS_URL=os.getenv("REDIS_URL")
BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL


celery_app = Celery(broker=BROKER_URL , backend=CELERY_RESULT_BACKEND)

@celery_app.task
def filework (text, thread_id , country):
    prompt = f"""You are a job recruiter evaluating candidates , you read their CV through {text} extracting main job keywords descending by job importance max 10 words
                            about the candidate"""
    upload = True
    chain = llmchain(os.getenv("GEMINI_API_KEY") , upload)
    response = chain.invoke(prompt)
    responseSTR=" ".join(response.keywords)
    print(responseSTR)
    with PostgresSaver.from_conn_string(os.getenv("DATABASE_URL")) as checkpointer:
        checkpointer.setup()
        agent = graph.compile(checkpointer=checkpointer)
        query, memory ,_= run_agent(agent ,responseSTR , thread_id, country)
    clean = normalize_jobs(query)
    jobs = filter_jobs(clean,memory)
    final_jobs = format_jobs_markdown(jobs , memory , country)
    return final_jobs



    