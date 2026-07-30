import asyncio
import re
import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from voice_agent import VoiceSession
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame


# matched as a whole first word, so "notion developer" stays a search
FEEDBACK_WORDS = {"no", "skip", "without", "not", "exclude"}
DETAIL_PREFIXES = ("tell me more", "more about", "details", "what about")
ORDINALS = {
    "first": 0, "one": 0, "1": 0,
    "second": 1, "two": 1, "2": 1,
    "third": 2, "three": 2, "3": 2,
    "fourth": 3, "four": 3, "4": 3,
    "fifth": 4, "five": 4, "5": 4,
}


def _speakable(text: str | None) -> str:
    """Descriptions arrive truncated mid-word with a trailing '...'. Cut back to
    the last finished sentence so it doesn't sound like the bot lost its train
    of thought."""
    text = (text or "").strip()
    if not text:
        return "No description available."
    text = text.removesuffix("...").strip()
    end = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if end > 40:
        return text[: end + 1]
    # no sentence break early enough — drop the dangling last word instead
    return text.rsplit(" ", 1)[0] + "."


class LangGraphProcessor(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = VoiceSession()
        self._last_processed_message = None
        self.shown_jobs = []

    def _print_jobs(self, jobs):
        """Full list with links goes to the terminal — speaking a URL is useless."""
        print(f"\n{'=' * 70}\n{len(jobs)} jobs\n{'=' * 70}", flush=True)
        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job.get('position')} — {job.get('company')}", flush=True)
            print(f"   {job.get('location')} | {job.get('salary')}", flush=True)
            print(f"   {job.get('apply_url')}\n", flush=True)

    def _describe(self, message):
        """Spoken detail for one job the user asked about."""
        if not self.shown_jobs:
            return "Search for something first, then ask me about a specific job."

        index = next((i for word, i in ORDINALS.items() if word in message), None)
        if index is None:
            # fall back to matching a company or role name they said
            index = next(
                (i for i, j in enumerate(self.shown_jobs)
                 if (j.get("company") or "").lower() in message
                 or (j.get("position") or "").lower() in message),
                None,
            )
        if index is None or index >= len(self.shown_jobs):
            return "I didn't catch which one. Try 'tell me more about the first one'."

        job = self.shown_jobs[index]
        location = job.get("location") or "not specified"
        salary = job.get("salary") or ""
        if not re.sub(r"[\s\-0]", "", salary):
            salary = "not listed"

        return (
            f"{job.get('position')} at {job.get('company')}. "
            f"Location: {location}. Salary: {salary}. "
            f"{_speakable(job.get('description'))} "
            f"The apply link is number {index + 1} in your terminal."
        )

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return

        last_user_message = frame.context.messages[-1]["content"]
        if last_user_message == self._last_processed_message:
            return
        self._last_processed_message = last_user_message

        command = last_user_message.strip().lower()
        t0 = time.perf_counter()
        print(f"[{time.strftime('%H:%M:%S')}] PROCESSOR got: {last_user_message!r}", flush=True)

        if command.startswith(DETAIL_PREFIXES):
            await self.push_frame(TTSSpeakFrame(text=self._describe(command)), direction)
            return

        # the graph no longer interrupts to ask, so the wording decides what to do.
        # these run off the event loop: they do blocking HTTP and LLM calls, and
        # blocking here freezes audio, VAD and interruption handling for the pipeline.
        words = re.findall(r"\w+", command)
        first_word = words[0] if words else ""

        if first_word == "reset":
            result = await asyncio.to_thread(self.session.reset)
        elif first_word in FEEDBACK_WORDS:
            result = await asyncio.to_thread(self.session.resume, last_user_message)
        else:
            result = await asyncio.to_thread(self.session.run, last_user_message)

        print(f"[{time.strftime('%H:%M:%S')}] AGENT took {time.perf_counter()-t0:.2f}s", flush=True)

        jobs = result["data"]
        self.shown_jobs = jobs

        if jobs:
            self._print_jobs(jobs)
            names = [f"{j.get('position')} at {j.get('company')}" for j in jobs[:2]]
            response_text = (
                f"{len(jobs)} jobs. Top two: {'; '.join(names)}. "
                "The full list with links is on your screen. "
                "Ask me for details, or tell me what to skip."
            )
        else:
            response_text = (
                "Nothing matched. Say reset to clear your filters, or try another search."
            )

        await self.push_frame(TTSSpeakFrame(text=response_text), direction)
