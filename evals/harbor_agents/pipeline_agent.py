from pathlib import Path
from typing import override

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HARNESS_FILES = ("agent.py", "mcp_server.py")


class PipelineAgent(BaseAgent):
    """Runs the repository's own job-search pipeline as the Harbor agent.

    No model is involved: search and filtering became fully deterministic when
    the LLM left the search path. The adapter uploads the harness unchanged,
    hands it the instruction, and records what it produced.
    """

    SUPPORTS_WINDOWS: bool = False

    @staticmethod
    @override
    def name() -> str:
        return "jobsearch-pipeline"

    @override
    def version(self) -> str:
        return "1.0.0"

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        return

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        instruction_path = self.logs_dir / "instruction.md"
        instruction_path.write_text(instruction, encoding="utf-8")
        await environment.upload_file(instruction_path, "/app/instruction.md")

        for name in HARNESS_FILES:
            await environment.upload_file(REPO / name, f"/app/{name}")
        await environment.upload_file(HERE / "run_pipeline.py", "/app/run_pipeline.py")

        result = await environment.exec("python /app/run_pipeline.py", cwd="/app")

        (self.logs_dir / "run.txt").write_text(
            f"return_code={result.return_code}\n"
            f"--- stdout ---\n{result.stdout or ''}\n"
            f"--- stderr ---\n{result.stderr or ''}\n",
            encoding="utf-8",
        )
