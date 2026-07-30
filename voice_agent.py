import uuid
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
import os
from agent import graph , normalize_jobs , filter_jobs 

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
            {"user_input": user_input, "fetched_jobs": []},
            config=config
        )

        self.last_jobs =normalize_jobs(result.get("clean_jobs", []))
        return {"type": "jobs", "data": filter_jobs(self.last_jobs , self.memory)}

        
    def reset(self):
        self.memory = []
        return {"type": "jobs", "data": filter_jobs(self.last_jobs, self.memory)}

    def resume(self, feedback):
        extraction_prompt = f"""Extract the job keywords to avoid from this user feedback.
            Return only a comma-separated list of keywords, nothing else.
            IMPORTANT: Only extract what to AVOID, not what the user wants to find.
            Do not include terms like "AI engineer", "python developer" etc.
            Example: "no stack" → "full stack, MERN, MEAN, frontend"
            Feedback: {feedback}"""
        keywords_str = chain.invoke(extraction_prompt)
        self.memory.append(keywords_str)
        filtered = filter_jobs(self.last_jobs , self.memory)
        return {"type": "jobs", "data": filtered}
        