from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from scratch_project.observability import TraceLevel
from scratch_project.tools.custom_tool import get_stock_data


@CrewBase
class ScratchProject:
    """ScratchProject crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    trace_level: TraceLevel = TraceLevel.FULL
    crew_log_path: str | None = None

    # =====================================Agent=====================================

    @agent
    def collector(self) -> Agent:
        return Agent(
            config=self.agents_config["collector"],
            tools=[get_stock_data],
            verbose=self.trace_level is TraceLevel.FULL,
        )

    @agent
    def summarizer(self) -> Agent:
        return Agent(
            config=self.agents_config["summarizer"],
            verbose=self.trace_level is TraceLevel.FULL,
        )

    @agent
    def risk_checker(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_checker"],
            verbose=self.trace_level is TraceLevel.FULL,
        )

    @agent
    def brief_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["brief_writer"],
            verbose=self.trace_level is TraceLevel.FULL,
        )

    # =====================================Task=====================================

    @task
    def collect_task(self) -> Task:
        return Task(config=self.tasks_config["collect_task"])

    @task
    def summarize_task(self) -> Task:
        return Task(config=self.tasks_config["summarize_task"])

    @task
    def risk_task(self) -> Task:
        return Task(config=self.tasks_config["risk_task"])

    @task
    def brief_task(self) -> Task:
        return Task(config=self.tasks_config["brief_task"])

    # =====================================Crew=====================================

    @crew
    def crew(self) -> Crew:
        """Creates the ScratchProject crew"""

        # Sequential means each task receives the output from earlier tasks.
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=self.trace_level is TraceLevel.FULL,
            output_log_file=(str(self.crew_log_path) if self.crew_log_path else None),
        )
