import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from voice_agent import VoiceSession
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame


class LangGraphProcessor(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = VoiceSession()
        self.waiting_for_answer = False
        self._last_processed_message = None

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMContextFrame):
            last_user_message = frame.context.messages[-1]["content"]

            if last_user_message == self._last_processed_message:
                return
            self._last_processed_message = last_user_message

            if self.waiting_for_answer:
                result = self.session.resume(last_user_message)
            else:
                result = self.session.run(last_user_message)

            if result["type"] == "question":
                self.waiting_for_answer = True
                response_text = result["text"]
            elif result["type"] == "jobs":
                jobs = result["data"]
                if jobs:
                    titles = [f"{j.get('title') or j.get('position', 'a role')} at {j.get('companyName') or j.get('company_name', 'a company')}" for j in jobs[:3]]
                    response_text = f"I found {len(jobs)} jobs. Here are a few: {'; '.join(titles)}."
                else:
                    response_text = "I didn't find any matching jobs."

            await self.push_frame(TTSSpeakFrame(text=response_text), direction)
        else:
            await self.push_frame(frame, direction)
