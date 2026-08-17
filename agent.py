from typing import TypedDict,Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send 
from datetime import datetime
import urllib.parse
import requests
import re
import sys
import html

SENIORITY = frozenset({"senior", "sr",  "junior" ,"júnior", "jr", "lead",
                       "principal", "staff", "mid", "entry" ,"pleno" , "sênior" , "estágio" , "head" , "director" , "vp" , "chief"})

GENERIC = frozenset({"engineering", "software", "developer" , "dev" , "engineer",
                     "remote", "job", "jobs", "work", "role", "position",
                     "specialist", "expert", "manager"})


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


def signal_tokens(query: str) -> list[str]:
    """The words of the query that carry meaning. Falls back to every word when
    the query is nothing but generic ones, so "developer job" still matches."""
    tokens = re.findall(r'\w+', query.lower())
    return [t for t in tokens if t not in GENERIC] or tokens

TAG_LIMIT = 3
ENOUGH = 50


def distinctive_tokens(query: str) -> list[str]:
    """The words that narrow the search, in order, deduplicated and capped.

    RemoteOK and Jobicy take one tag at a time, and picking the wrong word costs
    almost every result: `?tags=fullstack` returns 1 listing where `?tags=react`
    returns 101. Rather than guess which word matters, the fetchers try these in
    order and stop as soon as one comes back full, so a normal query still costs
    one request. Empty means no word narrows anything, and the caller should ask
    without a tag instead."""
    seen = []
    for token in re.findall(r'\w+', query.lower()):
        if token not in GENERIC and token not in seen:
            seen.append(token)
    return seen[:TAG_LIMIT]


def job_title(job: dict) -> str:
    """The title, however the source spells the field. Lowercased for matching."""
    return (job.get("title") or job.get("position", "") or job.get("jobTitle", "") or "").lower()


def title_hit(token: str, title: str) -> bool:
    """A token matches a whole word, optionally with a plural, version or `js`
    suffix.

    Substring matching was the earlier rule for tokens of four characters or
    more, which let "rust" fire on "anti-trust" and would let "java" fire on
    "javascript". Only prefixes were ever the problem, so suffixes stay allowed:
    "python" hits "python3", "react" hits "reactjs", "agent" hits "agents"."""
    return re.search(rf'\b{re.escape(token)}(?:js|s|\d+)?\b', title) is not None


def score_job(job: dict, query: str) -> float:
    """How well a job matches the query. A title hit outweighs any number of
    description hits, so >= TITLE_WEIGHT means "matched in the title"."""
    title = job_title(job)
    description = (job.get("description") or job.get("jobDescription", "")
                   or job.get("excerpt", "") or job.get("jobExcerpt", "") or "").lower()
    signal = signal_tokens(query)
    words = re.findall(r'\w+', query.lower())
    gen= [w for w in words if w in GENERIC]
    if len(words) == len(gen):
        gen_hits = 0
    else:
        gen_hits = sum(1 for g in gen if title_hit(g ,title) )   
    desc_words = re.findall(r'\w+', description)
    freq = sum(desc_words.count(s) for s in signal)
    bonus = freq/8
    title_hits = sum(1 for s in signal if title_hit(s, title))
    desc_hits = sum(1 for s in signal if s in desc_words)
    hits = min(desc_hits+gen_hits + bonus , 9) + title_hits*TITLE_WEIGHT 
    return hits


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
        salary = j.get("salary") or f"{j.get('salary_min', '')} - {j.get('salary_max', '')}" or f"{j.get('minSalary', '')} - {j.get('maxSalary', '')}"
        clean_salary = re.sub(r'[\s\-0]', '', f"{salary}")
        if not clean_salary:
            salary = "Salary not listed"
        job_hash = re.sub(r'[^a-z0-9]', '', f"{company.lower()}{position.lower()}")
        if job_hash in seen_hashes:
            continue
        seen_hashes.add(job_hash)
        clean_jobs.append({
            "company": fix_mojibake(" ".join(company.split())),
            "position": fix_mojibake(" ".join(position.split())),
            "location": fix_mojibake(j.get("location") or j.get("jobGeo") or j.get("candidate_required_location") or ", ".join(j.get("locationRestrictions") or [])).strip(", "),
            "description": fix_mojibake(strip_html(j.get("description") or j.get("excerpt", "") or j.get("jobExcerpt" , ""))),
            "salary": salary,
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
        signal = signal_tokens(state["user_input"])
        tags = distinctive_tokens(state["user_input"])
        try:
            raw = {}
            for tag in tags or [None]:
                url = "https://remoteok.com/api"
                if tag:
                    url += f"?tags={urllib.parse.quote(tag)}"
                response = requests.get(
                        url,
                        allow_redirects=False,
                        headers={"User-Agent": "Mozilla/5.0"} , timeout=30
                    )
                if response.status_code != 200:
                    break
                page = [job for job in response.json() if isinstance(job, dict)]
                for job in page:
                    raw.setdefault(job.get("url") or job.get("id"), job)
                if len(page) >= ENOUGH:
                    break
            fetched_jobs = [job for job in raw.values()
                            if any(title_hit(token, job_title(job)) for token in signal)]
            return {"fetched_jobs": fetched_jobs}
        except requests.exceptions.RequestException as e:
            print(f"Error {e}", file=sys.stderr)
            return {"fetched_jobs": []}
        
def fetch_sjobs(state:State):
        if not state.get("user_input"):
            return {"fetched_jobs": []}
        query = urllib.parse.quote(state['user_input'])
        try:
            response= requests.get(f"https://himalayas.app/jobs/api/search?q={query}&worldwide=true&sort=recent" , timeout=30)
            if response.status_code == 429:
                return {"fetched_jobs": []}
            data = response.json()
            fetched_jobs = data.get("jobs" , [])
            return {"fetched_jobs": fetched_jobs}
        except requests.exceptions.RequestException as e:
                print(f"Error {e}", file=sys.stderr)
                return {"fetched_jobs": []}

def fetch_tjobs(state:State):
    if not state.get("user_input"):
        return {"fetched_jobs": []}
    query = urllib.parse.quote(state['user_input'])
    try:
        response= requests.get(f"https://remotive.com/api/remote-jobs?search={query}", timeout=30)
        if response.status_code == 429:
            return {"fetched_jobs": []}
        data = response.json() 
        fetched_jobs = data.get("jobs" , []) 
        return {"fetched_jobs": fetched_jobs}
    except requests.exceptions.RequestException as e:
            print(f"Error {e}", file=sys.stderr)
            return {"fetched_jobs": []}
    
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
    tags = distinctive_tokens(state['user_input'])
    try:
        raw = {}
        for tag in tags or [None]:
            url = "https://jobicy.com/api/v2/remote-jobs"
            if tag:
                url += f"?tag={urllib.parse.quote(tag)}"
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                break
            page = response.json().get("jobs", [])
            for job in page:
                raw.setdefault(job.get("url") or job.get("id"), job)
            if len(page) >= ENOUGH:
                break
        return {"fetched_jobs": list(raw.values())}
    except requests.exceptions.RequestException as e:
        print(f"Error {e}", file=sys.stderr)
        return {"fetched_jobs": []}

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










