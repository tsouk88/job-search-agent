from typing import TypedDict,Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send 
from datetime import datetime
import urllib.parse
import requests
import re
import textwrap
import html

SENIORITY = frozenset({"senior", "sr",  "junior" ,"júnior", "jr", "lead",
                       "principal", "staff", "mid", "entry" ,"pleno" , "sênior" , "estágio" , "head" , "director" , "vp" , "chief"})

GENERIC = frozenset({"engineer", "engineering", "developer", "dev", "software",
                     "remote", "job", "jobs", "work", "role", "position",
                     "specialist", "expert", "manager"})


MIN_RESULTS = 8
TITLE_WEIGHT = 10
MAX_RESULTS = 12

def add_or_reset(existing: list, new: list | None) -> list:
    if new is None:
        return []
    return existing + new

def filter_jobs(jobs: list, memory: list ,  title_only=SENIORITY) -> list:
    keywords = []
    for entry in memory:
            keywords.extend([k.strip() for k in entry.split(",") if k.strip()])
    kept=[]
    for job in jobs:
        title = job.get("title") or job.get("position", "") or job.get("jobTitle" , "") or ""
        description = job.get("description") or job.get("excerpt", "") or job.get("jobExcerpt" , "")
        location= job.get("location") or job.get("jobGeo") or job.get("candidate_required_location") or ", ".join(job.get("locationRestrictions") or [])
        text = f"{title} {description} {location}".lower()
        title_words = set(re.findall(r'\w+', title.lower()))
        full_words = set(re.findall(r'\w+', text))
        blocked = False
        for kw in keywords:
            keyw = re.findall(r'\w+', kw.lower())
            target=  title_words if any(w in title_only for w in keyw) else full_words
            if any(w in target for w in keyw):
                blocked = True
                break
        if not blocked:
            kept.append(job)
    kept = [job for job in kept if job.get("apply_url") and job.get("position") not in ("", "Unknown")]
    return kept


def score_job(job: dict, query: str) -> int:
    """How well a job matches the query. A title hit outweighs any number of
    description hits, so >= TITLE_WEIGHT means "matched in the title"."""
    title = (job.get("title") or job.get("position", "") or job.get("jobTitle", "") or "").lower()
    description = (job.get("description") or job.get("jobDescription", "")
                   or job.get("excerpt", "") or job.get("jobExcerpt", "") or "").lower()
    tokens = re.findall(r'\w+', query.lower())
    signal = [t for t in tokens if t not in GENERIC] or tokens
    title_words = set(re.findall(r'\w+', title))
    desc_words = set(re.findall(r'\w+', description))
    title_hits = sum(1 for s in signal if ((s in title_words) if len(s) < 4 else (s in title)))
    desc_hits = sum(1 for s in signal if s in desc_words)
    return title_hits * TITLE_WEIGHT + desc_hits


def is_relevant(job: dict, query: str, strict: bool = True) -> bool:
    if not query:
        return True
    score = score_job(job, query)
    if strict:
        return score >= TITLE_WEIGHT
    return score > 0



def clean_description(text):
    clean = re.sub(r'<[^>]+>', '', text)
    return textwrap.shorten(clean, width=150, placeholder="...")

def strip_html(text):
    clean = re.sub(r'<[^>]+>', '', text)
    full_clean = html.unescape(clean)
    return full_clean

def fix_mojibake(text: str) -> str:
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def normalize_jobs(jobs):
    seen_hashes = set()
    clean_jobs = []
    for j in jobs:
        company = j.get("company") or j.get("companyName") or j.get("company_name") or "Unknown"
        position = j.get("title") or j.get("position", "") or j.get("jobTitle" , "") or "Unknown"
        job_hash = re.sub(r'[^a-z0-9]', '', f"{company.lower()}{position.lower()}")
        if job_hash in seen_hashes:
            continue
        seen_hashes.add(job_hash)
        clean_jobs.append({
            "company": fix_mojibake(company.strip()),
            "position": fix_mojibake(position.strip()),
            "location": fix_mojibake(j.get("location") or j.get("jobGeo") or j.get("candidate_required_location") or ", ".join(j.get("locationRestrictions") or [])).strip(", "),
            "description": fix_mojibake(clean_description(j.get("description") or j.get("excerpt", "") or j.get("jobExcerpt" , ""))),
            "salary": j.get("salary") or f"{j.get('salary_min', '')} - {j.get('salary_max', '')}" or f"{j.get('minSalary', '')} - {j.get('maxSalary', '')}",
            "apply_url": j.get("apply_url") or j.get("url") or j.get("applicationLink")
            })
    return clean_jobs


class State(TypedDict):
    fetched_jobs: Annotated[list[dict], add_or_reset]
    clean_jobs: list[dict]
    last_fetch_time: str
    current_job: dict
    user_input: str = ""
    memory: Annotated[list[str], add_or_reset]


  
   
def fetch_jobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        first_keyword = state['user_input'].split()[0].lower()
        query = urllib.parse.quote(first_keyword)
        response = requests.get(
                f"https://remoteok.com/api?tags={query}",
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0"}
            )
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = [job for job in data 
        if isinstance(job, dict) and
        any(keyword.lower() in [t.lower() for t in job.get("tags", [])]
        or keyword.lower() in job.get("position", "").lower()
        for keyword in state["user_input"].split())][:10]
        return {"fetched_jobs": fetched_jobs}
        
def fetch_sjobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        query = urllib.parse.quote(state['user_input'])
        response= requests.get(f"https://himalayas.app/jobs/api/search?q={query}&worldwide=true&sort=recent")
        if response.status_code == 429:
            return {"fetched_jobs": []}
        data = response.json()
         # Limit to 10 jobs for cost control — remove [:10] to search all jobs
        fetched_jobs = data["jobs"][:10]  
        return {"fetched_jobs": fetched_jobs}

def fetch_tjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    query = urllib.parse.quote(state['user_input'])
    response= requests.get(f"https://remotive.com/api/remote-jobs?search={query}")
    if response.status_code == 429:
        return {"fetched_jobs": []}
    data = response.json() 
    fetched_jobs = data["jobs"][:10]  
    return {"fetched_jobs": fetched_jobs}

#def fetch_fijobs(state:State):
#    if not state.get("user_input"):
#        return {"fetched_jobs": []}
#    response= requests.get("https://arbeitnow.com/api/job-board-api")
#    data = response.json()
#    fetched_jobs = [job for job in data["data"] 
#    if job.get("remote") == True
#    and job.get("location", "").lower() in ["", "remote", "worldwide"]
#    and any(keyword.lower() in job.get("title", "").lower() or 
#            keyword.lower() in job.get("description", "").lower()
#            for keyword in state["user_input"].split())][:10]
#    for job in fetched_jobs:
#        job["description"] = job.get("description", "")[:100]
#    return {"fetched_jobs": fetched_jobs}

def fetch_fjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    query = urllib.parse.quote(state['user_input'])
    response= requests.get(f"https://jobicy.com/api/v2/remote-jobs?tag={query}")
    if response.status_code == 429:
        return {"fetched_jobs": []}
    data = response.json() 
    fetched_jobs = data.get("jobs", [])[:10] 
    return {"fetched_jobs": fetched_jobs}

def collect_results(state: State):
    seen = set()
    unique_jobs = []
    query = state.get("user_input")
    for job in state["fetched_jobs"]:
            key = job.get("apply_url") or job.get("url") or job.get("applicationLink")
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
    scored = [(score_job(job, query), job) for job in unique_jobs]
    matched = [pair for pair in scored if pair[0] >= TITLE_WEIGHT]
    if len(matched) < MIN_RESULTS:
        matched = [pair for pair in scored if pair[0] > 0]
    matched.sort(key=lambda pair: pair[0], reverse=True)
    matched = matched[:MAX_RESULTS]
    correct_jobs = []
    for _, job in matched:
        description = job.get("jobDescription", "") or job.get("description", "")
        job["description"] = strip_html(description)[:500]
        correct_jobs.append(job)
    if len(correct_jobs) == 0:
        return {"clean_jobs": correct_jobs, "fetched_jobs": None }
    else :
        return {"clean_jobs": correct_jobs, "fetched_jobs": None , "last_fetch_time": datetime.now().isoformat()}


        

def fan_out(state:State):
     return [
        Send("fetch_jobs", state),   
        Send("fetch_sjobs", state),  
        Send("fetch_tjobs", state),
        Send("fetch_fjobs", state)
       # Send("fetch_fijobs", state)    
    ]


graph = StateGraph(State)
graph.add_node("fetch_jobs" , fetch_jobs)
graph.add_node("fetch_sjobs" , fetch_sjobs)
graph.add_node("fetch_tjobs" , fetch_tjobs)
graph.add_node("fetch_fjobs", fetch_fjobs)
#graph.add_node("fetch_fijobs", fetch_fijobs)
graph.add_node("collect_results", collect_results)



graph.add_conditional_edges(START, fan_out)
graph.add_edge("fetch_jobs", "collect_results")
graph.add_edge("fetch_sjobs", "collect_results")
graph.add_edge("fetch_tjobs", "collect_results")
graph.add_edge("fetch_fjobs", "collect_results")
graph.add_edge("collect_results", END)










