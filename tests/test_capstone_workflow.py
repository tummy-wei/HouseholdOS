from __future__ import annotations

import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from householdos.agents.capstone import (
    ChiefOfStaffSupervisor,
    CriticSafetyAgent,
    HouseholdPlanningAgent,
    ResearchKnowledgeAgent,
    ScheduleCommitmentsAgent,
)
from householdos.domain.capstone import AgentRole, CapstonePlanningRequest
from householdos.domain.schedule import RecurringActivity
from householdos.evaluation.harness import run_capstone_benchmark
from householdos.infrastructure.sqlite import SQLitePlanRepository
from householdos.retrieval.keyword import KeywordKnowledgeRepository
from householdos.workflows.capstone_weekly import CapstoneWeeklyPlanningWorkflow
from householdos.workflows.schedule_analysis import ScheduleAnalysisWorkflow


ROOT = Path(__file__).resolve().parents[1]


class CapstoneWorkflowTests(unittest.TestCase):
    def test_golden_workflow_persists_complete_brief_and_visible_route(self) -> None:
        activity = RecurringActivity(
            activity_id="soccer",
            person="Student A",
            title="Soccer training",
            weekday=0,
            start_time=time(17),
            end_time=time(19),
            location="Highland Middle School",
        )
        analysis = ScheduleAnalysisWorkflow().run(
            date(2026, 9, 7), [], [activity]
        )
        request = CapstonePlanningRequest(
            week_start=date(2026, 9, 7),
            objective="Plan family schedule and church preparation",
            priorities=["Prepare Friday fellowship reminder"],
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLitePlanRepository(Path(directory) / "test.db")
            repository.initialize()
            workflow = CapstoneWeeklyPlanningWorkflow(
                ScheduleCommitmentsAgent(),
                ResearchKnowledgeAgent(
                    KeywordKnowledgeRepository(ROOT / "data/knowledge_items.json")
                ),
                HouseholdPlanningAgent(),
                CriticSafetyAgent(),
                ChiefOfStaffSupervisor(),
                repository,
            )

            brief, trace = workflow.run(request, analysis, [])

            self.assertTrue(brief.validation.passed)
            self.assertEqual(len(brief.days), 7)
            self.assertTrue(brief.grocery_list)
            self.assertTrue(brief.logistics)
            self.assertIn(AgentRole.RESEARCH, trace.route)
            self.assertEqual(len(set(trace.route)), 5)
            self.assertIsNotNone(repository.latest_capstone_run())

    def test_repeatable_benchmark_contains_twenty_scenarios(self) -> None:
        result = run_capstone_benchmark(str(ROOT / "data/knowledge_items.json"))

        self.assertEqual(result.total, 20)
        self.assertEqual(result.passed, 20)
        self.assertEqual(result.unsafe_action_rate, 0)


if __name__ == "__main__":
    unittest.main()
