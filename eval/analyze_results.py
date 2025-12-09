"""
Results Analysis and Performance Insights

Analyzes eval results to identify opportunities for improving agent performance.
Examines: prompts, autonomy, reflection, tool usage, error patterns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from eval.schemas import ExperimentResults

logger = structlog.get_logger(__name__)


class PerformanceAnalyzer:
    """Analyzes eval results to identify improvement opportunities."""

    def __init__(self, results_path: str):
        """
        Initialize analyzer with results file.

        Args:
            results_path: Path to experiment results JSON
        """
        with open(results_path) as f:
            data = json.load(f)
            self.results = ExperimentResults.model_validate(data)

    def analyze(self) -> dict[str, Any]:
        """
        Perform comprehensive analysis.

        Returns:
            Analysis report with insights and recommendations
        """
        report = {
            "summary": self._analyze_summary(),
            "success_patterns": self._analyze_success_patterns(),
            "failure_patterns": self._analyze_failure_patterns(),
            "performance_metrics": self._analyze_performance(),
            "recommendations": self._generate_recommendations(),
        }

        return report

    def _analyze_summary(self) -> dict[str, Any]:
        """Generate high-level summary statistics."""
        tasks = self.results.tasks
        completed = [t for t in tasks if t.status == "completed"]
        failed = [t for t in tasks if t.status == "failed"]
        
        # Judge metrics (critical)
        judged_tasks = [t for t in tasks if t.judge_overall is not None]
        accepted = [t for t in judged_tasks if t.judge_recommendation == "accept"]
        needs_review = [t for t in judged_tasks if t.judge_recommendation == "needs_review"]
        rejected = [t for t in judged_tasks if t.judge_recommendation == "reject"]

        summary = {
            "total_tasks": len(tasks),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / len(tasks) if tasks else 0,
            "avg_duration": (
                sum(t.duration_seconds for t in tasks if t.duration_seconds) / len(tasks)
                if tasks
                else 0
            ),
            "avg_files_changed": (
                sum(t.files_changed_count for t in tasks if t.files_changed_count) / len(tasks)
                if tasks
                else 0
            ),
            "avg_fix_attempts": (
                sum(t.fix_attempts_count for t in tasks if t.fix_attempts_count) / len(tasks)
                if tasks
                else 0
            ),
        }
        
        # Add judge metrics if available
        if judged_tasks:
            summary["judge_metrics"] = {
                "judged_count": len(judged_tasks),
                "avg_overall": sum(t.judge_overall for t in judged_tasks) / len(judged_tasks),
                "avg_correctness": sum(t.judge_correctness for t in judged_tasks if t.judge_correctness) / len([t for t in judged_tasks if t.judge_correctness]),
                "avg_style": sum(t.judge_style for t in judged_tasks if t.judge_style) / len([t for t in judged_tasks if t.judge_style]),
                "avg_architecture": sum(t.judge_architecture for t in judged_tasks if t.judge_architecture) / len([t for t in judged_tasks if t.judge_architecture]),
                "avg_safety": sum(t.judge_safety for t in judged_tasks if t.judge_safety) / len([t for t in judged_tasks if t.judge_safety]),
                "accepted": len(accepted),
                "needs_review": len(needs_review),
                "rejected": len(rejected),
                "accept_rate": len(accepted) / len(judged_tasks),
            }
        
        return summary

    def _analyze_success_patterns(self) -> dict[str, Any]:
        """Identify patterns in successful tasks."""
        completed = [t for t in self.results.tasks if t.status == "completed"]

        if not completed:
            return {"message": "No completed tasks to analyze"}

        test_pass_rate = (
            len([t for t in completed if t.tests_exit_code == 0]) / len(completed)
            if completed
            else 0
        )

        return {
            "count": len(completed),
            "test_pass_rate": test_pass_rate,
            "avg_duration": (
                sum(t.duration_seconds for t in completed if t.duration_seconds) / len(completed)
            ),
            "avg_files": (
                sum(t.files_changed_count for t in completed if t.files_changed_count)
                / len(completed)
            ),
            "low_fix_attempts": len([t for t in completed if (t.fix_attempts_count or 0) <= 1]),
            "insights": [
                f"Test pass rate: {test_pass_rate:.1%}",
                f"Average {sum(t.files_changed_count or 0 for t in completed) / len(completed):.1f} files per task",
                f"{len([t for t in completed if (t.fix_attempts_count or 0) == 0])} tasks completed without fixes",
            ],
        }

    def _analyze_failure_patterns(self) -> dict[str, Any]:
        """Identify patterns in failed tasks."""
        failed = [t for t in self.results.tasks if t.status == "failed"]

        if not failed:
            return {"message": "No failed tasks - excellent!"}

        error_types = {}
        for task in failed:
            if task.error_message:
                # Extract error type from message
                error_type = task.error_message.split(":")[0] if ":" in task.error_message else "Unknown"
                error_types[error_type] = error_types.get(error_type, 0) + 1

        return {
            "count": len(failed),
            "error_types": error_types,
            "high_fix_attempts": len([t for t in failed if (t.fix_attempts_count or 0) > 2]),
            "timeout_likely": len([t for t in failed if t.duration_seconds and t.duration_seconds > 1000]),
            "insights": [
                f"Most common error: {max(error_types.items(), key=lambda x: x[1])[0] if error_types else 'N/A'}",
                f"{len([t for t in failed if (t.fix_attempts_count or 0) > 2])} tasks exceeded fix attempts",
            ],
        }

    def _analyze_performance(self) -> dict[str, Any]:
        """Analyze performance metrics."""
        tasks = self.results.tasks

        return {
            "duration_distribution": {
                "min": min((t.duration_seconds for t in tasks if t.duration_seconds), default=0),
                "max": max((t.duration_seconds for t in tasks if t.duration_seconds), default=0),
                "avg": (
                    sum(t.duration_seconds for t in tasks if t.duration_seconds) / len(tasks)
                    if tasks
                    else 0
                ),
            },
            "fix_attempts_distribution": {
                "zero": len([t for t in tasks if (t.fix_attempts_count or 0) == 0]),
                "one": len([t for t in tasks if (t.fix_attempts_count or 0) == 1]),
                "two_plus": len([t for t in tasks if (t.fix_attempts_count or 0) >= 2]),
            },
            "files_changed_distribution": {
                "small": len([t for t in tasks if (t.files_changed_count or 0) <= 3]),
                "medium": len([t for t in tasks if 3 < (t.files_changed_count or 0) <= 7]),
                "large": len([t for t in tasks if (t.files_changed_count or 0) > 7]),
            },
        }

    def _generate_recommendations(self) -> dict[str, list[str]]:
        """Generate actionable recommendations for improvement."""
        summary = self._analyze_summary()
        success = self._analyze_success_patterns()
        failure = self._analyze_failure_patterns()

        recommendations = {
            "prompt_improvements": [],
            "autonomy_adjustments": [],
            "reflection_enhancements": [],
            "workflow_changes": [],
            "tool_usage": [],
        }

        # CRITICAL: Judge-based recommendations (highest priority)
        judge_metrics = summary.get("judge_metrics")
        if judge_metrics:
            accept_rate = judge_metrics["accept_rate"]
            avg_overall = judge_metrics["avg_overall"]
            avg_correctness = judge_metrics["avg_correctness"]
            avg_safety = judge_metrics["avg_safety"]
            
            # Accept rate is the primary quality signal
            if accept_rate < 0.5:
                recommendations["prompt_improvements"].insert(0,
                    f"🚨 CRITICAL: Only {accept_rate:.0%} accept rate - major prompt overhaul needed"
                )
                recommendations["workflow_changes"].insert(0,
                    "Add mandatory self-review step before submission"
                )
            elif accept_rate < 0.7:
                recommendations["prompt_improvements"].insert(0,
                    f"⚠️  Accept rate {accept_rate:.0%} below target - refine agent prompts"
                )
            
            # Overall quality score
            if avg_overall < 6:
                recommendations["reflection_enhancements"].insert(0,
                    f"🚨 Low quality score ({avg_overall:.1f}/10) - add quality gates before completion"
                )
            elif avg_overall < 7.5:
                recommendations["prompt_improvements"].append(
                    f"Quality score {avg_overall:.1f}/10 - emphasize best practices in prompts"
                )
            
            # Correctness issues
            if avg_correctness < 7:
                recommendations["prompt_improvements"].insert(0,
                    f"🚨 CRITICAL: Low correctness ({avg_correctness:.1f}/10) - agents not completing tasks properly"
                )
                recommendations["reflection_enhancements"].insert(0,
                    "Add 'verify_requirements_met' step before marking complete"
                )
            
            # Safety concerns
            if avg_safety > 3:
                recommendations["prompt_improvements"].insert(0,
                    f"🚨 SECURITY: High safety risk ({avg_safety:.1f}/10) - add security guidelines to all prompts"
                )
                recommendations["tool_usage"].insert(0,
                    "Add security scanning tool to detect vulnerabilities"
                )
        
        # Analyze success rate
        if summary["success_rate"] < 0.7:
            recommendations["prompt_improvements"].append(
                "Low success rate - consider more explicit task decomposition in planner prompt"
            )
            recommendations["workflow_changes"].append(
                "Add pre-flight validation step before code generation"
            )

        # Analyze fix attempts
        if summary["avg_fix_attempts"] > 1.5:
            recommendations["reflection_enhancements"].append(
                "High fix attempts - add self-reflection step after code generation"
            )
            recommendations["prompt_improvements"].append(
                "Enhance QA agent prompt to provide more specific fix guidance"
            )

        # Analyze test pass rate
        if isinstance(success, dict) and success.get("test_pass_rate", 1.0) < 0.8:
            recommendations["prompt_improvements"].append(
                "Low test pass rate - emphasize test-driven development in coder prompt"
            )
            recommendations["tool_usage"].append(
                "Add 'run_tests_before_commit' tool to catch issues earlier"
            )

        # Analyze duration
        if summary["avg_duration"] > 600:
            recommendations["autonomy_adjustments"].append(
                "Long durations - consider parallel execution of independent steps"
            )
            recommendations["workflow_changes"].append(
                "Add timeout warnings and progress checkpoints"
            )

        # Analyze failure patterns
        if isinstance(failure, dict) and failure.get("high_fix_attempts", 0) > 0:
            recommendations["reflection_enhancements"].append(
                "Add 'analyze_previous_attempt' reflection before retry"
            )
            recommendations["autonomy_adjustments"].append(
                "Increase max_fix_attempts or add escalation to human review"
            )

        # General recommendations
        if not any(recommendations.values()):
            recommendations["prompt_improvements"].append(
                "Performance is good - consider A/B testing prompt variations"
            )

        return recommendations

    def print_report(self):
        """Print formatted analysis report."""
        report = self.analyze()

        print("\n" + "=" * 80)
        print("PERFORMANCE ANALYSIS REPORT")
        print("=" * 80)

        print("\n📊 SUMMARY")
        print("-" * 80)
        summary = report["summary"]
        print(f"Total Tasks: {summary['total_tasks']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Avg Duration: {summary['avg_duration']:.1f}s")
        print(f"Avg Files Changed: {summary['avg_files_changed']:.1f}")
        print(f"Avg Fix Attempts: {summary['avg_fix_attempts']:.1f}")
        
        # Judge metrics (most important)
        if "judge_metrics" in summary:
            print("\n🎯 JUDGE EVALUATION (CRITICAL)")
            print("-" * 80)
            jm = summary["judge_metrics"]
            print(f"Tasks Judged: {jm['judged_count']}")
            print(f"Accept Rate: {jm['accept_rate']:.1%} ({jm['accepted']} accepted, {jm['needs_review']} need review, {jm['rejected']} rejected)")
            print(f"\nAverage Scores (0-10):")
            print(f"  Overall Quality: {jm['avg_overall']:.1f}")
            print(f"  Correctness: {jm['avg_correctness']:.1f}")
            print(f"  Style: {jm['avg_style']:.1f}")
            print(f"  Architecture: {jm['avg_architecture']:.1f}")
            print(f"  Safety Risk: {jm['avg_safety']:.1f} (lower is better)")

        print("\n✅ SUCCESS PATTERNS")
        print("-" * 80)
        success = report["success_patterns"]
        if isinstance(success, dict) and "insights" in success:
            for insight in success["insights"]:
                print(f"  • {insight}")

        print("\n❌ FAILURE PATTERNS")
        print("-" * 80)
        failure = report["failure_patterns"]
        if isinstance(failure, dict) and "insights" in failure:
            for insight in failure["insights"]:
                print(f"  • {insight}")

        print("\n📈 PERFORMANCE METRICS")
        print("-" * 80)
        perf = report["performance_metrics"]
        print(f"Duration: {perf['duration_distribution']['min']:.0f}s - {perf['duration_distribution']['max']:.0f}s")
        print(f"Fix Attempts: 0={perf['fix_attempts_distribution']['zero']}, 1={perf['fix_attempts_distribution']['one']}, 2+={perf['fix_attempts_distribution']['two_plus']}")

        print("\n💡 RECOMMENDATIONS")
        print("=" * 80)
        recs = report["recommendations"]

        if recs["prompt_improvements"]:
            print("\n🎯 Prompt Improvements:")
            for rec in recs["prompt_improvements"]:
                print(f"  • {rec}")

        if recs["autonomy_adjustments"]:
            print("\n🤖 Autonomy Adjustments:")
            for rec in recs["autonomy_adjustments"]:
                print(f"  • {rec}")

        if recs["reflection_enhancements"]:
            print("\n🔍 Reflection Enhancements:")
            for rec in recs["reflection_enhancements"]:
                print(f"  • {rec}")

        if recs["workflow_changes"]:
            print("\n⚙️  Workflow Changes:")
            for rec in recs["workflow_changes"]:
                print(f"  • {rec}")

        if recs["tool_usage"]:
            print("\n🛠️  Tool Usage:")
            for rec in recs["tool_usage"]:
                print(f"  • {rec}")

        print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m eval.analyze_results <results_json_path>")
        print("Example: python -m eval.analyze_results eval/results/exp_phase1_baseline.json")
        sys.exit(1)

    results_path = sys.argv[1]
    if not Path(results_path).exists():
        print(f"Error: Results file not found: {results_path}")
        sys.exit(1)

    analyzer = PerformanceAnalyzer(results_path)
    analyzer.print_report()


if __name__ == "__main__":
    main()
