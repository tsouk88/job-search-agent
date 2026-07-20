import uuid
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
import os
from agent import graph

llm = init_chat_model(
    model="google_genai:gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1,
    max_retries=10
)
chain = llm | StrOutputParser()
checkpointer = MemorySaver() 
compiled_agent = graph.compile(checkpointer=checkpointer)

class VoiceSession:
    def __init__(self):
        self.memory = []
        self.thread_id = str(uuid.uuid4())
        self.last_query = ""
        self.last_jobs = []

    def run(self, user_input):
        config = {"configurable": {"thread_id": self.thread_id}}
        result = compiled_agent.invoke(
            {"user_input": user_input, "fetched_jobs": [], "memory": self.memory},
            config=config
        )

        if "__interrupt__" in result:
            question = result["__interrupt__"][0].value
            self.last_jobs = result.get("clean_jobs", [])  
            jobs = self._filter_jobs(self.last_jobs)
            if jobs:
                response_text = f"I found {len(jobs)} jobs. {question}"
            else:
                response_text = question
            return {"type": "question", "text": response_text}

        self.memory = result.get("memory", [])
        return {"type": "jobs", "data": self._filter_jobs(result.get("clean_jobs", []))}

    def _filter_jobs(self, jobs):
        if not self.memory:
            return jobs
        all_keywords = []
        for entry in self.memory:
            all_keywords.extend([k.strip() for k in entry.split(",") if k.strip()])
        filtered = []
        for job in jobs:
            title = (job.get("title") or job.get("position") or "").lower()
            if not any(keyword.lower() in title for keyword in all_keywords):
                filtered.append(job)
        return filtered
        
    def resume(self, feedback):
        config = {"configurable": {"thread_id": self.thread_id}}
        extraction_prompt = f"""Extract the job keywords to avoid from this user feedback.
            Return only a comma-separated list of keywords, nothing else.
            IMPORTANT: Only extract what to AVOID, not what the user wants to find.
            Do not include terms like "AI engineer", "python developer" etc.
            Example: "no stack" → "full stack, MERN, MEAN, frontend"
            Feedback: {feedback}"""
        keywords_str = chain.invoke(extraction_prompt)
        compiled_agent.invoke(Command(resume=keywords_str), config=config)
        self.memory.append(keywords_str)
        filtered = self._filter_jobs(self.last_jobs)
        if filtered:
            return {"type": "jobs", "data": filtered}
        else:
            return {"type": "jobs", "data": []}