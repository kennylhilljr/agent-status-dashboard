#!/usr/bin/env python3
"""Demonstration of artifact detection for all agent types.

This script demonstrates the artifact detection system in action,
showing how different agent outputs are parsed to extract artifacts.
"""

from artifact_detector import get_artifact_detector


def demo_coding_agent():
    """Demonstrate artifact detection for coding agent."""
    print("\n" + "=" * 70)
    print("CODING AGENT ARTIFACT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    # Simulate coding agent output
    output = """
    Implementation complete for AI-53:

    Created new file artifact_detector.py with detection logic
    Modified agent_metrics_collector.py to add artifact support
    Updated orchestrator.py to integrate detector

    Running comprehensive test suite...
    ============================= 66 passed in 0.06s ===============================

    All tasks completed successfully!
    """

    artifacts = detector.detect_artifacts("coding", output)

    print("\nAgent Output:")
    print(output)
    print("\nDetected Artifacts:")
    for artifact in artifacts:
        print(f"  - {artifact}")

    return artifacts


def demo_github_agent():
    """Demonstrate artifact detection for GitHub agent."""
    print("\n" + "=" * 70)
    print("GITHUB AGENT ARTIFACT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    output = """
    GitHub workflow for AI-53:

    Created branch feature/ai-53-artifact-detection
    Committed abc123f: Add artifact detector module
    Committed def456a: Add comprehensive tests
    Committed 789beef: Update orchestrator integration

    Created PR #125: Add artifact detection per agent type
    PR approved and merged #125
    """

    artifacts = detector.detect_artifacts("github", output)

    print("\nAgent Output:")
    print(output)
    print("\nDetected Artifacts:")
    for artifact in artifacts:
        print(f"  - {artifact}")

    return artifacts


def demo_linear_agent():
    """Demonstrate artifact detection for Linear agent."""
    print("\n" + "=" * 70)
    print("LINEAR AGENT ARTIFACT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    output = """
    Linear updates:

    Created issue AI-200: Implement new dashboard feature
    Updated issue AI-53 status to Done
    Transitioned issue AI-199 to In Progress

    Added comment to AI-200 with implementation plan
    Posted comment on AI-199 with progress update
    """

    artifacts = detector.detect_artifacts("linear", output)

    print("\nAgent Output:")
    print(output)
    print("\nDetected Artifacts:")
    for artifact in artifacts:
        print(f"  - {artifact}")

    return artifacts


def demo_slack_agent():
    """Demonstrate artifact detection for Slack agent."""
    print("\n" + "=" * 70)
    print("SLACK AGENT ARTIFACT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    output = """
    Notifications sent:

    Sent message to #engineering: AI-53 implementation complete
    Posted notification to #status-updates: All tests passing
    Sent message to @tech-lead: Ready for review
    """

    artifacts = detector.detect_artifacts("slack", output)

    print("\nAgent Output:")
    print(output)
    print("\nDetected Artifacts:")
    for artifact in artifacts:
        print(f"  - {artifact}")

    return artifacts


def demo_pr_reviewer_agent():
    """Demonstrate artifact detection for PR reviewer agent."""
    print("\n" + "=" * 70)
    print("PR REVIEWER AGENT ARTIFACT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    output = """
    PR Review for #125:

    Completed review on PR #125: Add artifact detection

    Code quality: Excellent
    Test coverage: Comprehensive (66 tests)
    Documentation: Complete

    Approved pull request #125
    Ready to merge!
    """

    artifacts = detector.detect_artifacts("pr_reviewer", output)

    print("\nAgent Output:")
    print(output)
    print("\nDetected Artifacts:")
    for artifact in artifacts:
        print(f"  - {artifact}")

    return artifacts


def demo_bash_output_detection():
    """Demonstrate detection from Bash tool output."""
    print("\n" + "=" * 70)
    print("BASH OUTPUT DETECTION")
    print("=" * 70)

    detector = get_artifact_detector()

    # Git status output
    git_status = """
    On branch main
    Changes to be committed:
      new file:   artifact_detector.py
      new file:   tests/test_artifact_detection.py
      modified:   agents/orchestrator.py
    """

    # Pytest output
    pytest_output = """
    ============================= test session starts ==============================
    collected 66 items

    tests/test_artifact_detection.py::TestCodingAgentArtifacts::test_detect_file_created PASSED
    ...
    ============================= 66 passed in 0.06s ===============================
    """

    print("\nGit Status Output:")
    print(git_status)
    artifacts_git = detector.detect_from_bash_output("coding", git_status)
    print("\nDetected Artifacts:")
    for artifact in artifacts_git:
        print(f"  - {artifact}")

    print("\n" + "-" * 70)
    print("\nPytest Output:")
    print(pytest_output)
    artifacts_pytest = detector.detect_from_bash_output("coding", pytest_output)
    print("\nDetected Artifacts:")
    for artifact in artifacts_pytest:
        print(f"  - {artifact}")

    return artifacts_git + artifacts_pytest


def demo_tool_specific_detection():
    """Demonstrate detection from specific MCP tools."""
    print("\n" + "=" * 70)
    print("TOOL-SPECIFIC DETECTION (MCP Tools)")
    print("=" * 70)

    detector = get_artifact_detector()

    # Linear create_issue
    print("\nLinear create_issue tool:")
    artifacts_linear = detector.detect_from_tool_name(
        agent_name="linear",
        tool_name="mcp__claude_ai_Linear__create_issue",
        tool_input={"title": "New feature"},
        tool_output='{"success": true, "issue": {"id": "AI-53"}}'
    )
    print(f"  Tool: Linear create_issue")
    print(f"  Output: Created issue AI-53")
    print(f"  Detected: {artifacts_linear}")

    # GitHub CreatePullRequest
    print("\nGitHub CreatePullRequest tool:")
    artifacts_github = detector.detect_from_tool_name(
        agent_name="github",
        tool_name="mcp__claude_ai_ai-cli-macz__Github_CreatePullRequest",
        tool_input={"title": "Add feature"},
        tool_output='{"number": 125, "url": "https://github.com/..."}'
    )
    print(f"  Tool: GitHub CreatePullRequest")
    print(f"  Output: PR #125 created")
    print(f"  Detected: {artifacts_github}")

    # GitHub SubmitPullRequestReview (Approve)
    print("\nGitHub SubmitPullRequestReview (Approve):")
    artifacts_review = detector.detect_from_tool_name(
        agent_name="pr_reviewer",
        tool_name="mcp__claude_ai_ai-cli-macz__Github_SubmitPullRequestReview",
        tool_input={"pull_number": 125, "event": "APPROVE"},
        tool_output='{"success": true}'
    )
    print(f"  Tool: GitHub SubmitPullRequestReview")
    print(f"  Input: APPROVE PR #125")
    print(f"  Detected: {artifacts_review}")

    return artifacts_linear + artifacts_github + artifacts_review


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("ARTIFACT DETECTION DEMONSTRATION")
    print("AI-53: Add artifact detection per agent type")
    print("=" * 70)

    all_artifacts = []

    # Run all demos
    all_artifacts.extend(demo_coding_agent())
    all_artifacts.extend(demo_github_agent())
    all_artifacts.extend(demo_linear_agent())
    all_artifacts.extend(demo_slack_agent())
    all_artifacts.extend(demo_pr_reviewer_agent())
    all_artifacts.extend(demo_bash_output_detection())
    all_artifacts.extend(demo_tool_specific_detection())

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal artifacts detected: {len(all_artifacts)}")
    print("\nArtifact breakdown by type:")

    # Count by type
    artifact_types = {}
    for artifact in all_artifacts:
        artifact_type = artifact.split(":")[0]
        artifact_types[artifact_type] = artifact_types.get(artifact_type, 0) + 1

    for artifact_type, count in sorted(artifact_types.items()):
        print(f"  - {artifact_type}: {count}")

    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
