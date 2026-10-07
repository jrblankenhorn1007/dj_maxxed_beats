// Scenario: MBProject confinement, reviewable edits, confirmed apply, backups, undo.
// argv: workDir repoRoot
(
var args = thisProcess.argv, here = thisProcess.nowExecutingPath.dirname;
(here +/+ "harness.scd").load;
~work = args[0];
~root = ~work +/+ "project";

AppClock.sched(240, { "MBTEST FAIL watchdog :: scenario timed out".postln; 1.exit; nil });

Routine {
	var project, outcome, proposal, edit, comp, original, backups, spec, reserved;
	try {
		comp = ~root +/+ "comp.scd";
		original = ~readText.(comp);

		~check.("open_missing_dir_is_io_error",
			~throwsKind.({ MBProject.open(~work +/+ "does-not-exist") }, \io));
		project = MBProject.open(~root);
		~check.("open_resolves_real_root", project.root == File.realpath(~root), project.root);

		~check.("files_lists_project_sources",
			project.files.includesEqual("comp.scd") and: { project.files.includesEqual("sub/notes.md") },
			project.files);
		~check.("files_excludes_hidden_data_renders_and_symlinks",
			project.files.every { |path|
				path.beginsWith(".").not and: { path.beginsWith("renders/").not }
				and: { path.find("link").isNil } and: { path.find(".maxxedbeats").isNil }
			},
			project.files);

		[
			"../outside.scd", "/etc/passwd", "sub/../../outside.scd", "~/x.scd", "",
			"sub//notes.md", "sub/./notes.md", "dirlink/escape.scd", "filelink.scd",
			"a\\b.scd", "C:/x.scd", nil, 42
		].do { |bad, index|
			~check.("resolve_rejects_" ++ index,
				~throwsKind.({ project.resolve(bad) }, \validation), bad.asCompileString);
		};
		~check.("resolve_accepts_nested_new_path",
			MBProject.comparablePath(project.resolve("sub/new/thing.scd"))
				== MBProject.comparablePath(project.root +/+ "sub/new/thing.scd"));
		~check.("read_returns_contents", project.read("comp.scd") == original);
		~check.("read_rejects_symlink_escape", ~throwsKind.({ project.read("filelink.scd") }, \validation));
		~check.("read_missing_is_io_error", ~throwsKind.({ project.read("missing.scd") }, \io));

		reserved = [
			["data", { |p| p.dataDir }],
			["renders", { |p| p.rendersDir }],
			["backups", { |p| p.backupsDir }],
			["sessions", { |p| p.sessionsDir }],
			["render-work", { |p| MBProject.writeFile(p.dataDir +/+ "renders/id/test.txt", "escape") }],
			["nested", { |p| MBProject.writeFile(p.backupsDir +/+ "id/after/sub/test.txt", "escape") }]
		];
		reserved.do { |entry|
			["link", "file"].do { |kind|
				var p = MBProject.open(~work +/+ (entry[0] ++ "-" ++ kind));
				~check.("reserved_" ++ entry[0] ++ "_" ++ kind ++ "_rejected",
					~throwsKind.({ entry[1].value(p) }, \validation));
			}
		};
		reserved = MBProject.open(~root +/+ "sub");
		[".maxxedbeats", "renders", ".maxxedbeats/backups", ".maxxedbeats/sessions"].do { |path|
			reserved.directory(path)
		};
		~check.("reserved_directories_are_created",
			[reserved.dataDir, reserved.rendersDir, reserved.backupsDir, reserved.sessionsDir]
				.every { |path| File.type(path) == \directory });
		File.delete(reserved.sessionsDir);
		~writeText.(~root +/+ "sub/.maxxedbeats/sessions", "not a folder");
		~check.("reserved_access_revalidates", ~throwsKind.({ reserved.sessionsDir }, \validation));

		[
			(path: ".maxxedbeats/x.scd", action: "create", newText: "1"),
			(path: "renders/x.scd", action: "create", newText: "1"),
			(path: ".hidden.scd", action: "create", newText: "1"),
			(path: "Evil.sc", action: "create", newText: "1"),
			(path: "comp.scd", action: "create", newText: "1"),
			(path: "missing.scd", action: "edit", oldText: "a", newText: "b"),
			(path: "comp.scd", action: "edit", oldText: "not present", newText: "b"),
			(path: "comp.scd", action: "edit", oldText: "dup", newText: "b"),
			(path: "comp.scd", action: "edit", oldText: "", newText: "b"),
			(path: "comp.scd", action: "replace", newText: original),
			(path: "comp.scd", action: "rename", newText: "x"),
			(path: "../escape.scd", action: "create", newText: "1"),
			(path: "Renders/x.scd", action: "create", newText: "1"),
			(path: "RENDERS/x.scd", action: "create", newText: "1")
		].do { |badSpec, index|
			~check.("prepare_edit_rejects_" ++ index,
				~throwsKind.({ project.prepareEdit(badSpec) }, \validation), badSpec);
		};

		edit = project.prepareEdit((path: "comp.scd", action: "edit",
			oldText: "~tempo = 100;", newText: "~tempo = 128;"));
		~check.("edit_exposes_contract_fields",
			edit.path == "comp.scd" and: { edit.oldText == "~tempo = 100;" }
			and: { edit.newText == "~tempo = 128;" } and: { edit.isNew == false },
			[edit.path, edit.oldText, edit.newText, edit.isNew]);
		~check.("edit_diff_is_unified",
			edit.diffString.contains("--- a/comp.scd") and: { edit.diffString.contains("+++ b/comp.scd") }
			and: { edit.diffString.contains("\n-~tempo = 100;") }
			and: { edit.diffString.contains("\n+~tempo = 128;") }
			and: { edit.diffString.contains("@@ -") },
			edit.diffString);
		~check.("edit_diff_keeps_context_small",
			edit.diffString.contains("line 1\n").not, edit.diffString);

		proposal = (
			plan: "Raise the tempo.", summary: "Tempo 100 -> 128 and a new pad file.",
			edits: [edit, project.prepareEdit((path: "sub/pad.scd", action: "create", newText: "// pad\n1 + 1\n"))]
		);
		~check.("new_file_diff_uses_dev_null",
			proposal[\edits][1].isNew and: { proposal[\edits][1].diffString.contains("--- /dev/null") }
			and: { proposal[\edits][1].diffString.contains("+// pad") },
			proposal[\edits][1].diffString);

		outcome = ~await.({ |ok, fail| project.apply(proposal, false, ok, fail) });
		~check.("apply_refuses_without_confirmation", ~failedWith.(outcome, \validation), ~describe.(outcome));
		outcome = ~await.({ |ok, fail| project.apply(proposal, "yes", ok, fail) });
		~check.("apply_refuses_truthy_non_boolean", ~failedWith.(outcome, \validation), ~describe.(outcome));
		~check.("unconfirmed_apply_leaves_files_untouched",
			~readText.(comp) == original and: { File.exists(~root +/+ "sub/pad.scd").not }
			and: { project.backups.isEmpty });

		outcome = ~await.({ |ok, fail| project.apply(proposal, true, ok, fail) });
		~check.("confirmed_apply_succeeds", outcome[0] == \ok, ~describe.(outcome));
		~check.("apply_writes_edits",
			~readText.(comp) == original.replace("~tempo = 100;", "~tempo = 128;")
			and: { ~readText.(~root +/+ "sub/pad.scd") == "// pad\n1 + 1\n" });
		backups = project.backups;
		~check.("apply_records_backup_first",
			backups.size == 1 and: { backups[0][\undone] == false }
			and: { backups[0][\paths].asArray.sort == ["comp.scd", "sub/pad.scd"] }
			and: { ~readText.(project.dataDir +/+ "backups" +/+ backups[0][\id] +/+ "before/comp.scd") == original },
			backups);
		~check.("apply_result_reports_backup",
			outcome[1][\backupId] == backups[0][\id] and: { outcome[1][\paths].size == 2 }, outcome[1]);

		outcome = ~await.({ |ok, fail| project.apply(proposal, true, ok, fail) });
		~check.("reapplying_stale_proposal_is_refused", ~failedWith.(outcome, \validation), ~describe.(outcome));

		outcome = ~await.({ |ok, fail| project.undo(ok, fail) });
		~check.("undo_succeeds", outcome[0] == \ok, ~describe.(outcome));
		~check.("undo_restores_and_removes_created_files",
			~readText.(comp) == original and: { File.exists(~root +/+ "sub/pad.scd").not });
		~check.("undo_marks_backup_undone", project.backups[0][\undone] == true, project.backups);
		outcome = ~await.({ |ok, fail| project.undo(ok, fail) });
		~check.("undo_with_nothing_to_undo_fails", ~failedWith.(outcome, \validation), ~describe.(outcome));

		// External change between proposal and apply.
		edit = project.prepareEdit((path: "comp.scd", action: "replace", newText: "// replaced\n"));
		~writeText.(comp, original ++ "// user edit\n");
		outcome = ~await.({ |ok, fail| project.apply((plan: "p", summary: "s", edits: [edit]), true, ok, fail) });
		~check.("apply_refuses_when_file_changed_since_proposal",
			~failedWith.(outcome, \validation) and: { ~readText.(comp) == (original ++ "// user edit\n") },
			~describe.(outcome));
		~writeText.(comp, original);

		// Undo must not destroy edits the user made after applying.
		edit = project.prepareEdit((path: "comp.scd", action: "replace", newText: "// v2\n"));
		outcome = ~await.({ |ok, fail| project.apply((plan: "p", summary: "s", edits: [edit]), true, ok, fail) });
		~check.("second_apply_succeeds", outcome[0] == \ok, ~describe.(outcome));
		~writeText.(comp, "// v2\n// user kept typing\n");
		outcome = ~await.({ |ok, fail| project.undo(ok, fail) });
		~check.("undo_refuses_to_overwrite_later_user_changes",
			~failedWith.(outcome, \validation) and: { ~readText.(comp) == "// v2\n// user kept typing\n" },
			~describe.(outcome));
		~writeText.(comp, "// v2\n");
		outcome = ~await.({ |ok, fail| project.undo(ok, fail) });
		~check.("undo_after_revert_restores_original", outcome[0] == \ok and: { ~readText.(comp) == original },
			~describe.(outcome));

		outcome = ~await.({ |ok, fail| project.apply((plan: "p", summary: "s", edits: []), true, ok, fail) });
		~check.("apply_rejects_empty_edit_list", ~failedWith.(outcome, \validation), ~describe.(outcome));
		outcome = ~await.({ |ok, fail| project.apply((plan: "p", summary: "s", edits: ["comp.scd"]), true, ok, fail) });
		~check.("apply_rejects_non_edit_objects", ~failedWith.(outcome, \validation), ~describe.(outcome));
		spec = [
			(path: "alias.scd", action: "create", newText: "first"),
			(path: "ALIAS.scd", action: "create", newText: "second")
		];
		outcome = ~await.({ |ok, fail|
			project.apply((edits: spec.collect { |item| project.prepareEdit(item) }), true, ok, fail)
		});
		~check.("apply_rejects_case_aliases", ~failedWith.(outcome, \validation), ~describe.(outcome));
		~check.("response_rejects_case_aliases",
			~throwsKind.({ MBResponseFormat.parse(~proposalJSON.(spec), project) }, \validation));
		~check.("case_aliases_leave_files_untouched",
			File.exists(~root +/+ "alias.scd").not and: { File.exists(~root +/+ "ALIAS.scd").not });
		~check.("outside_file_never_touched", ~readText.(~work +/+ "outside.scd") == "// outside\n");
	} { |error|
		~check.("uncaught_error", false, error.errorString);
	};
	~finish.value;
}.play(AppClock);
)
