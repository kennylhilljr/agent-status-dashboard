"""Comprehensive tests for artifact detection per agent type.

This test suite verifies artifact detection for all agent types:
- coding/coding_fast: files created/modified, tests run
- github: commits, PRs, branches
- linear: issues created/updated, comments
- slack: messages sent
- pr_reviewer: reviews, approvals, change requests
"""

import pytest

from artifact_detector import ArtifactDetector, get_artifact_detector


class TestCodingAgentArtifacts:
    """Test artifact detection for coding and coding_fast agents."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_file_created(self):
        """Test detection of file creation."""
        output = "Created file src/artifact_detector.py"
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "file:src/artifact_detector.py:created" in artifacts

    def test_detect_file_created_with_quotes(self):
        """Test detection of file creation with quotes."""
        output = 'Created new file `test.py`'
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "file:test.py:created" in artifacts

    def test_detect_file_modified(self):
        """Test detection of file modification."""
        output = "Modified agent_metrics_collector.py to add artifact tracking"
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "file:agent_metrics_collector.py:modified" in artifacts

    def test_detect_multiple_files(self):
        """Test detection of multiple file operations."""
        output = """
        Created file artifact_detector.py
        Modified orchestrator.py
        Updated test_metrics.py
        """
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "file:artifact_detector.py:created" in artifacts
        assert "file:orchestrator.py:modified" in artifacts
        assert "file:test_metrics.py:modified" in artifacts

    def test_detect_tests_run(self):
        """Test detection of test execution."""
        output = "Ran pytest with 25 tests passed"
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "tests_run:25" in artifacts

    def test_detect_tests_run_alternative_format(self):
        """Test detection of test execution in various formats."""
        test_cases = [
            ("Running pytest: 15 tests passed", "tests_run:15"),
            ("Executed 42 test cases", "tests_run:42"),
            ("pytest: 8 failed", "tests_run:8"),
        ]

        for output, expected in test_cases:
            artifacts = self.detector.detect_artifacts("coding", output)
            assert expected in artifacts

    def test_detect_test_file_creation(self):
        """Test detection of test file creation."""
        output = "Created test file test_artifact_detection.py"
        artifacts = self.detector.detect_artifacts("coding", output)

        assert "file:test_artifact_detection.py:created" in artifacts

    def test_coding_fast_agent_same_detection(self):
        """Test that coding_fast agent uses same detection as coding."""
        output = """
        Created utils.py
        Modified config.json
        Ran 10 tests
        """
        artifacts_coding = self.detector.detect_artifacts("coding", output)
        artifacts_fast = self.detector.detect_artifacts("coding_fast", output)

        # Both should detect the same artifacts
        assert artifacts_coding == artifacts_fast
        assert len(artifacts_coding) >= 2


class TestGithubAgentArtifacts:
    """Test artifact detection for github agent."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_commit(self):
        """Test detection of git commit."""
        output = "Created commit abc123f with message 'Add feature'"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "commit:abc123f" in artifacts

    def test_detect_commit_full_sha(self):
        """Test detection of commit with full SHA."""
        output = "Committed abc123f456789012345678901234567890abcd"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "commit:abc123f456789012345678901234567890abcd" in artifacts

    def test_detect_pr_created(self):
        """Test detection of PR creation."""
        output = "Created PR #42 for feature implementation"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "pr:42:created" in artifacts

    def test_detect_pr_created_alternative(self):
        """Test detection of PR creation with alternative wording."""
        output = "Opened pull request 123"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "pr:123:created" in artifacts

    def test_detect_pr_merged(self):
        """Test detection of PR merge."""
        output = "Merged pull request #99"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "pr:99:merged" in artifacts

    def test_detect_branch_created(self):
        """Test detection of branch creation."""
        output = "Created branch feature/artifact-detection"
        artifacts = self.detector.detect_artifacts("github", output)

        assert "branch:feature/artifact-detection:created" in artifacts

    def test_detect_multiple_git_operations(self):
        """Test detection of multiple git operations."""
        output = """
        Created branch ai-53-implementation
        Committed abc123f
        Created PR #55
        """
        artifacts = self.detector.detect_artifacts("github", output)

        assert "branch:ai-53-implementation:created" in artifacts
        assert "commit:abc123f" in artifacts
        assert "pr:55:created" in artifacts


class TestLinearAgentArtifacts:
    """Test artifact detection for linear agent."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_issue_created(self):
        """Test detection of issue creation."""
        output = "Created issue AI-53 for artifact detection"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:AI-53:created" in artifacts

    def test_detect_issue_created_alternative(self):
        """Test detection of issue creation with alternative wording."""
        output = "Opened ticket PROJECT-123"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:PROJECT-123:created" in artifacts

    def test_detect_issue_updated(self):
        """Test detection of issue update."""
        output = "Updated issue AI-50 status to In Progress"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:AI-50:updated" in artifacts

    def test_detect_issue_transitioned(self):
        """Test detection of issue transition."""
        output = "Transitioned ticket AI-51 to Done"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:AI-51:updated" in artifacts

    def test_detect_comment_added(self):
        """Test detection of comment addition."""
        output = "Added comment to AI-52 with test results"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "comment:AI-52:added" in artifacts

    def test_detect_comment_posted(self):
        """Test detection of posted comment."""
        output = "Posted comment on ticket AI-100"
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "comment:AI-100:added" in artifacts

    def test_detect_multiple_linear_operations(self):
        """Test detection of multiple Linear operations."""
        output = """
        Created issue AI-200
        Updated issue AI-199
        Added comment to AI-198
        """
        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:AI-200:created" in artifacts
        assert "issue:AI-199:updated" in artifacts
        assert "comment:AI-198:added" in artifacts


class TestSlackAgentArtifacts:
    """Test artifact detection for slack agent."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_message_sent_to_channel(self):
        """Test detection of message sent to channel."""
        output = "Sent message to #engineering channel"
        artifacts = self.detector.detect_artifacts("slack", output)

        assert "message:#engineering:sent" in artifacts

    def test_detect_message_sent_to_user(self):
        """Test detection of message sent to user."""
        output = "Posted notification to @user123"
        artifacts = self.detector.detect_artifacts("slack", output)

        assert "message:@user123:sent" in artifacts

    def test_detect_message_with_quotes(self):
        """Test detection of message with channel in quotes."""
        output = 'Sent message to channel `#general`'
        artifacts = self.detector.detect_artifacts("slack", output)

        assert "message:#general:sent" in artifacts

    def test_detect_multiple_slack_messages(self):
        """Test detection of multiple Slack messages."""
        output = """
        Sent message to #engineering
        Posted notification to #status-updates
        """
        artifacts = self.detector.detect_artifacts("slack", output)

        assert "message:#engineering:sent" in artifacts
        assert "message:#status-updates:sent" in artifacts


class TestPRReviewerAgentArtifacts:
    """Test artifact detection for pr_reviewer and pr_reviewer_fast agents."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_review_completed(self):
        """Test detection of PR review completion."""
        output = "Completed review on PR #42"
        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "review:42:completed" in artifacts

    def test_detect_review_submitted(self):
        """Test detection of PR review submission."""
        output = "Submitted PR review for #123"
        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "review:123:completed" in artifacts

    def test_detect_approval(self):
        """Test detection of PR approval."""
        output = "Approved pull request #99"
        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "approval:99" in artifacts

    def test_detect_changes_requested(self):
        """Test detection of changes requested."""
        output = "Requested changes on PR #55"
        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "changes_requested:55" in artifacts

    def test_detect_changes_requested_alternative(self):
        """Test detection of changes requested with alternative wording."""
        output = "Changes requested for pull request #77"
        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "changes_requested:77" in artifacts

    def test_pr_reviewer_fast_same_detection(self):
        """Test that pr_reviewer_fast uses same detection as pr_reviewer."""
        output = """
        Completed review on PR #10
        Approved pull request #11
        Requested changes on PR #12
        """
        artifacts_standard = self.detector.detect_artifacts("pr_reviewer", output)
        artifacts_fast = self.detector.detect_artifacts("pr_reviewer_fast", output)

        assert artifacts_standard == artifacts_fast
        assert len(artifacts_standard) == 3


class TestOpsAgentArtifacts:
    """Test artifact detection for ops (composite) agent."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_ops_agent_detects_linear_artifacts(self):
        """Test that ops agent can detect Linear operations."""
        output = "Updated issue AI-50 to In Progress"
        artifacts = self.detector.detect_artifacts("ops", output)

        assert "issue:AI-50:updated" in artifacts

    def test_ops_agent_detects_slack_artifacts(self):
        """Test that ops agent can detect Slack operations."""
        output = "Sent message to #team-updates"
        artifacts = self.detector.detect_artifacts("ops", output)

        assert "message:#team-updates:sent" in artifacts

    def test_ops_agent_detects_github_artifacts(self):
        """Test that ops agent can detect GitHub operations."""
        output = "Created branch feature/ops-test"
        artifacts = self.detector.detect_artifacts("ops", output)

        assert "branch:feature/ops-test:created" in artifacts


class TestBashOutputDetection:
    """Test detection from Bash tool output."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_from_git_log(self):
        """Test detection of commits from git log output."""
        bash_output = """
        commit abc123f456789012345678901234567890abcdef
        Author: Test User <test@example.com>
        Date: Mon Jan 1 12:00:00 2024

            Add feature
        """
        artifacts = self.detector.detect_from_bash_output("github", bash_output)

        assert "commit:abc123f" in artifacts

    def test_detect_from_git_status_new_files(self):
        """Test detection of new files from git status."""
        bash_output = """
        On branch main
        Changes to be committed:
          new file:   artifact_detector.py
          new file:   tests/test_artifact_detection.py
        """
        artifacts = self.detector.detect_from_bash_output("coding", bash_output)

        assert "file:artifact_detector.py:created" in artifacts
        assert "file:tests/test_artifact_detection.py:created" in artifacts

    def test_detect_from_git_status_modified_files(self):
        """Test detection of modified files from git status."""
        bash_output = """
        On branch main
        Changes not staged:
          modified:   orchestrator.py
          modified:   metrics.py
        """
        artifacts = self.detector.detect_from_bash_output("coding", bash_output)

        assert "file:orchestrator.py:modified" in artifacts
        assert "file:metrics.py:modified" in artifacts

    def test_detect_from_pytest_output(self):
        """Test detection of test runs from pytest output."""
        bash_output = """
        ============================= test session starts ==============================
        collected 42 items

        tests/test_artifact_detection.py::TestCodingAgentArtifacts::test_detect_file_created PASSED
        ...
        ============================= 42 passed in 1.23s ===============================
        """
        artifacts = self.detector.detect_from_bash_output("coding", bash_output)

        assert "tests_run:42" in artifacts

    def test_detect_from_gh_pr_create(self):
        """Test detection of PR from gh pr create output."""
        bash_output = """
        Creating pull request for feature-branch into main in owner/repo

        https://github.com/owner/repo/pull/123
        """
        artifacts = self.detector.detect_from_bash_output("github", bash_output)

        assert "pr:123:created" in artifacts


class TestToolSpecificDetection:
    """Test detection based on specific tool invocations."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_detect_from_write_tool(self):
        """Test detection from Write tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="coding",
            tool_name="Write",
            tool_input={"file_path": "/path/to/new_file.py"},
            tool_output="File written successfully"
        )

        assert "file:/path/to/new_file.py:created" in artifacts

    def test_detect_from_edit_tool(self):
        """Test detection from Edit tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="coding",
            tool_name="Edit",
            tool_input={"file_path": "/path/to/existing.py"},
            tool_output="File edited successfully"
        )

        assert "file:/path/to/existing.py:modified" in artifacts

    def test_detect_from_bash_tool(self):
        """Test detection from Bash tool (delegates to bash output parser)."""
        bash_output = "42 passed in 2.5s"
        artifacts = self.detector.detect_from_tool_name(
            agent_name="coding",
            tool_name="Bash",
            tool_input={"command": "pytest"},
            tool_output=bash_output
        )

        assert "tests_run:42" in artifacts

    def test_detect_from_linear_create_issue(self):
        """Test detection from Linear create_issue tool."""
        tool_output = '{"success": true, "issue": {"id": "AI-100", "title": "Test"}}'
        artifacts = self.detector.detect_from_tool_name(
            agent_name="linear",
            tool_name="mcp__claude_ai_Linear__create_issue",
            tool_input={"title": "Test issue"},
            tool_output=tool_output
        )

        assert "issue:AI-100:created" in artifacts

    def test_detect_from_linear_update_issue(self):
        """Test detection from Linear update_issue tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="linear",
            tool_name="mcp__claude_ai_Linear__update_issue",
            tool_input={"issue_id": "AI-50"},
            tool_output='{"success": true}'
        )

        assert "issue:AI-50:updated" in artifacts

    def test_detect_from_linear_create_comment(self):
        """Test detection from Linear create_comment tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="linear",
            tool_name="mcp__claude_ai_Linear__create_comment",
            tool_input={"issueId": "AI-75"},
            tool_output='{"success": true}'
        )

        assert "comment:AI-75:added" in artifacts

    def test_detect_from_github_create_pr(self):
        """Test detection from GitHub CreatePullRequest tool."""
        tool_output = '{"number": 456, "url": "https://github.com/..."}'
        artifacts = self.detector.detect_from_tool_name(
            agent_name="github",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_CreatePullRequest",
            tool_input={"title": "Test PR"},
            tool_output=tool_output
        )

        assert "pr:456:created" in artifacts

    def test_detect_from_github_merge_pr(self):
        """Test detection from GitHub MergePullRequest tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="github",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_MergePullRequest",
            tool_input={"pull_number": 789},
            tool_output='{"merged": true}'
        )

        assert "pr:789:merged" in artifacts

    def test_detect_from_github_create_branch(self):
        """Test detection from GitHub CreateBranch tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="github",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_CreateBranch",
            tool_input={"branch": "feature/test"},
            tool_output='{"success": true}'
        )

        assert "branch:feature/test:created" in artifacts

    def test_detect_from_github_submit_review_approve(self):
        """Test detection from GitHub SubmitPullRequestReview with approval."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="pr_reviewer",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_SubmitPullRequestReview",
            tool_input={"pull_number": 321, "event": "APPROVE"},
            tool_output='{"success": true}'
        )

        assert "approval:321" in artifacts

    def test_detect_from_github_submit_review_request_changes(self):
        """Test detection from GitHub SubmitPullRequestReview with changes requested."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="pr_reviewer",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_SubmitPullRequestReview",
            tool_input={"pullNumber": 654, "event": "REQUEST_CHANGES"},
            tool_output='{"success": true}'
        )

        assert "changes_requested:654" in artifacts

    def test_detect_from_github_submit_review_comment(self):
        """Test detection from GitHub SubmitPullRequestReview with comment only."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="pr_reviewer",
            tool_name="mcp__claude_ai_ai-cli-macz__Github_SubmitPullRequestReview",
            tool_input={"pull_number": 111, "event": "COMMENT"},
            tool_output='{"success": true}'
        )

        assert "review:111:completed" in artifacts

    def test_detect_from_slack_add_message(self):
        """Test detection from Slack add_message tool."""
        artifacts = self.detector.detect_from_tool_name(
            agent_name="slack",
            tool_name="mcp__slack__conversations_add_message",
            tool_input={"channel": "#team-updates"},
            tool_output='{"ok": true}'
        )

        assert "message:#team-updates:sent" in artifacts


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_empty_output_returns_empty_list(self):
        """Test that empty output returns empty artifact list."""
        artifacts = self.detector.detect_artifacts("coding", "")
        assert artifacts == []

    def test_no_matching_patterns(self):
        """Test output with no matching patterns."""
        output = "This is just some random text with no artifacts"
        artifacts = self.detector.detect_artifacts("coding", output)
        assert artifacts == []

    def test_unknown_agent_type(self):
        """Test that unknown agent type returns empty list."""
        output = "Created file test.py"
        artifacts = self.detector.detect_artifacts("unknown_agent", output)
        assert artifacts == []

    def test_duplicate_artifacts_deduplicated(self):
        """Test that duplicate artifacts are deduplicated."""
        output = """
        Created file test.py
        Created new file test.py
        Created file test.py
        """
        artifacts = self.detector.detect_artifacts("coding", output)

        # Should only have one entry
        assert artifacts.count("file:test.py:created") == 1

    def test_additional_context_used(self):
        """Test that additional context is included in detection."""
        tool_results = "Task completed successfully"
        additional_context = "Created branch feature/ai-53"

        artifacts = self.detector.detect_artifacts(
            "github",
            tool_results,
            additional_context
        )

        assert "branch:feature/ai-53:created" in artifacts

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        test_cases = [
            "CREATED FILE test.py",
            "Created File test.py",
            "created file test.py",
        ]

        for output in test_cases:
            artifacts = self.detector.detect_artifacts("coding", output)
            assert "file:test.py:created" in artifacts


class TestSingletonInstance:
    """Test the singleton instance getter."""

    def test_get_artifact_detector_returns_instance(self):
        """Test that get_artifact_detector returns a detector instance."""
        detector = get_artifact_detector()
        assert isinstance(detector, ArtifactDetector)

    def test_get_artifact_detector_returns_same_instance(self):
        """Test that get_artifact_detector returns the same instance."""
        detector1 = get_artifact_detector()
        detector2 = get_artifact_detector()
        assert detector1 is detector2


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.detector = ArtifactDetector()

    def test_coding_agent_full_workflow(self):
        """Test full coding workflow with multiple operations."""
        output = """
        Starting implementation of AI-53...

        Created file artifact_detector.py with detection logic
        Modified agent_metrics_collector.py to integrate detector
        Updated orchestrator.py to use artifact detection

        Created test file test_artifact_detection.py
        Running pytest...
        ============================= 85 passed in 3.2s ===============================

        All tasks completed successfully.
        """

        artifacts = self.detector.detect_artifacts("coding", output)

        # Should detect all artifacts
        assert "file:artifact_detector.py:created" in artifacts
        assert "file:agent_metrics_collector.py:modified" in artifacts
        assert "file:orchestrator.py:modified" in artifacts
        assert "file:test_artifact_detection.py:created" in artifacts
        assert "tests_run:85" in artifacts

    def test_github_agent_full_workflow(self):
        """Test full GitHub workflow."""
        output = """
        Created branch feature/ai-53-artifacts

        Committed abc123f: Add artifact detector
        Committed def456a: Add tests
        Committed 789beef: Update docs

        Created PR #125: Add artifact detection per agent type
        Approved pull request #125
        Merged PR #125 into main
        """

        artifacts = self.detector.detect_artifacts("github", output)

        assert "branch:feature/ai-53-artifacts:created" in artifacts
        assert "commit:abc123f" in artifacts
        assert "commit:def456a" in artifacts
        assert "commit:789beef" in artifacts
        assert "pr:125:created" in artifacts
        # Note: approval and merge might not be detected from plain text,
        # but would be from tool-specific detection

    def test_pr_reviewer_full_workflow(self):
        """Test full PR review workflow."""
        output = """
        Reviewing PR #125: Add artifact detection per agent type

        Checking code quality...
        - artifact_detector.py: Well structured
        - tests: Comprehensive coverage

        Completed review on PR #125
        Approved pull request #125
        """

        artifacts = self.detector.detect_artifacts("pr_reviewer", output)

        assert "review:125:completed" in artifacts
        assert "approval:125" in artifacts

    def test_linear_agent_full_workflow(self):
        """Test full Linear workflow."""
        output = """
        Created issue AI-200: Implement new feature
        Updated issue AI-199 to In Progress

        Added comment to AI-199 with status update
        Posted comment on AI-200 with plan

        Transitioned issue AI-199 to Done
        """

        artifacts = self.detector.detect_artifacts("linear", output)

        assert "issue:AI-200:created" in artifacts
        assert "issue:AI-199:updated" in artifacts
        assert "comment:AI-199:added" in artifacts
        assert "comment:AI-200:added" in artifacts

    def test_ops_agent_composite_workflow(self):
        """Test ops agent handling multiple artifact types."""
        output = """
        Updated issue AI-53 to In Progress
        Created branch feature/ai-53
        Sent message to #engineering with status
        """

        artifacts = self.detector.detect_artifacts("ops", output)

        assert "issue:AI-53:updated" in artifacts
        assert "branch:feature/ai-53:created" in artifacts
        assert "message:#engineering:sent" in artifacts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
