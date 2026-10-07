"""MBProject: path confinement, reviewable diffs, confirmed apply, backups, undo."""

import os
import unittest

from mb_workflow.harness import ScenarioTestCase, new_work_dir, run_scenario


ORIGINAL = "// comp\nline 1\nline 2\nline 3\nline 4\n~tempo = 100;\ndup\ndup\nline 5\n"


class MBProjectWorkflowTests(ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        work = new_work_dir("project")
        project = work / "project"
        (project / "sub").mkdir(parents=True)
        (project / "comp.scd").write_text(ORIGINAL)
        (project / "sub" / "notes.md").write_text("notes\n")
        (project / ".hidden.scd").write_text("hidden\n")
        (project / "renders").mkdir()
        (project / "renders" / "old.wav").write_bytes(b"RIFF")
        (work / "outside.scd").write_bytes(b"// outside\n")
        (work / "outside-dir").mkdir()
        os.symlink(str(work / "outside-dir"), str(project / "dirlink"))
        os.symlink(str(work / "outside.scd"), str(project / "filelink.scd"))
        for name, relative in (
            ("data", ".maxxedbeats"),
            ("renders", "renders"),
            ("backups", ".maxxedbeats/backups"),
            ("sessions", ".maxxedbeats/sessions"),
            ("render-work", ".maxxedbeats/renders"),
            ("nested", ".maxxedbeats/backups/id/after/sub"),
        ):
            for kind in ("link", "file"):
                reserved = work / (name + "-" + kind) / relative
                reserved.parent.mkdir(parents=True, exist_ok=True)
                if kind == "link":
                    os.symlink(str(work / "outside-dir"), str(reserved), target_is_directory=True)
                else:
                    reserved.write_text("not a directory")
        cls.scenario_run = run_scenario("project_scenario", work)

    def test_scenario_completed_without_failures(self):
        self.assertScenarioCompleted()

    def test_paths_are_confined_to_the_project(self):
        self.assertChecks(
            "open_missing_dir_is_io_error",
            "open_resolves_real_root",
            "files_lists_project_sources",
            "files_excludes_hidden_data_renders_and_symlinks",
            "resolve_accepts_nested_new_path",
            "read_returns_contents",
            "read_rejects_symlink_escape",
            "read_missing_is_io_error",
            *["resolve_rejects_{}".format(index) for index in range(13)]
        )

    def test_edits_are_validated_and_reviewable(self):
        self.assertChecks(
            "edit_exposes_contract_fields",
            "edit_diff_is_unified",
            "edit_diff_keeps_context_small",
            "new_file_diff_uses_dev_null",
            *["prepare_edit_rejects_{}".format(index) for index in range(14)]
        )

    def test_apply_requires_confirmation_and_backs_up(self):
        self.assertChecks(
            "apply_refuses_without_confirmation",
            "apply_refuses_truthy_non_boolean",
            "unconfirmed_apply_leaves_files_untouched",
            "confirmed_apply_succeeds",
            "apply_writes_edits",
            "apply_records_backup_first",
            "apply_result_reports_backup",
            "reapplying_stale_proposal_is_refused",
            "apply_refuses_when_file_changed_since_proposal",
            "apply_rejects_empty_edit_list",
            "apply_rejects_non_edit_objects",
            "outside_file_never_touched",
        )

    def test_undo_restores_safely(self):
        self.assertChecks(
            "undo_succeeds",
            "undo_restores_and_removes_created_files",
            "undo_marks_backup_undone",
            "undo_with_nothing_to_undo_fails",
            "second_apply_succeeds",
            "undo_refuses_to_overwrite_later_user_changes",
            "undo_after_revert_restores_original",
        )

    def test_reserved_paths_and_case_aliases_are_safe(self):
        self.assertChecks(
            "reserved_directories_are_created",
            "reserved_access_revalidates",
            "apply_rejects_case_aliases",
            "response_rejects_case_aliases",
            "case_aliases_leave_files_untouched",
            *["reserved_{}_{}_rejected".format(name, kind)
              for name in ("data", "renders", "backups", "sessions", "render-work", "nested")
              for kind in ("link", "file")],
        )


class MBAudioCheckResourceTests(ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenario_run = run_scenario("audio_resource_scenario", new_work_dir("audio-resource"))

    def test_soundfiles_close_on_every_exit(self):
        self.assertScenarioCompleted()
        self.assertChecks(
            "cancel_during_scan_has_open_file",
            "cancel_closes_file",
            "cancel_stops_callback",
            "stop_before_start_does_not_open",
            "normal_scan_closes_file",
            "error_scan_closes_file",
        )


if __name__ == "__main__":
    unittest.main()
