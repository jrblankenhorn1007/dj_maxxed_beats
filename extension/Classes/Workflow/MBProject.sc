/*
A user-selected composition project folder.

All paths are relative to root, validated by .resolve (no absolute paths,
"..", empty or "." components, backslashes, drive letters, control
characters, or symbolic links anywhere along the path). Editable paths are
also restricted to visible .scd/.md/.txt/.json files outside the reserved
.maxxedbeats/ and renders/ folders. .apply writes only after an explicit
confirmed == true, backs up first, verifies every write, and rolls back on
failure; .undo restores the newest applied backup unless the files changed
since. Callbacks run on AppClock.
*/
MBProject {
	classvar <>maxFileBytes = 262144, <>maxFiles = 400, <>maxDepth = 8, <>maxPathSize = 240;
	classvar <>editableExtensions = #["scd", "md", "txt", "json"];
	var <root, backupCounter = 0;

	*open { |dir|
		^super.new.initProject(dir)
	}

	*fail { |kind, detail| MBError(kind, detail).throw }

	*asMBError { |error, kind = \io|
		^if(error.isKindOf(MBError)) { error } { MBError(kind, error.errorString) }
	}

	*readFile { |absolutePath|
		var file = File(absolutePath, "rb"), text;
		if(file.isOpen.not) { this.fail(\io, "could not open " ++ absolutePath.basename ++ " for reading") };
		text = protect { file.readAllString } { file.close };
		^text ? ""
	}

	*writeFile { |absolutePath, text|
		var file;
		absolutePath = this.prepareWritePath(absolutePath);
		file = File(absolutePath, "wb");
		if(file.isOpen.not) { this.fail(\io, "could not open " ++ absolutePath.basename ++ " for writing") };
		protect { file.write(text) } { file.close };
		if(this.readFile(absolutePath) != text) {
			this.fail(\io, "verification failed after writing " ++ absolutePath.basename)
		};
	}

	*prepareWritePath { |absolutePath|
		var current = absolutePath, parent, type, missing = List.new;
		while {
			type = File.type(current);
			if(type == \symlink) { this.fail(\validation, "symbolic links are not allowed in write paths") };
			if(current != absolutePath and: { type != \not_found } and: { type != \directory }) {
				this.fail(\validation, "a write path component is not a folder")
			};
			if(current == absolutePath and: { type != \not_found } and: { type != \regular }) {
				this.fail(\validation, "the write destination is not a regular file")
			};
			if(current != absolutePath and: { type == \not_found }) { missing.add(current) };
			parent = current.dirname;
			parent != current and: { parent.notEmpty }
		} { current = parent };
		missing.reverseDo { |dir|
			File.mkdir(dir);
			if(File.type(dir) != \directory) { this.fail(\io, "could not create a write folder") };
		};
		^absolutePath
	}

	initProject { |dir|
		var real;
		if(dir.isString.not and: { dir.isKindOf(Symbol).not } or: { dir.asString.isEmpty }) {
			MBProject.fail(\validation, "choose a project folder")
		};
		real = File.realpath(dir.asString.standardizePath);
		if(real.isNil or: { File.type(real) != \directory }) {
			MBProject.fail(\io, "project folder does not exist: " ++ dir.asString)
		};
		real = real.withoutTrailingSlash;
		if(real.isEmpty or: { real == "/" } or: { real.size <= 3 and: { real.contains(":") } }) {
			MBProject.fail(\validation, "a filesystem root cannot be used as a project folder")
		};
		root = real;
	}

	dataDir { ^this.directory(".maxxedbeats", false) }
	rendersDir { ^this.directory("renders", false) }
	backupsDir { ^this.directory(".maxxedbeats/backups", false) }
	sessionsDir { ^this.directory(".maxxedbeats/sessions", false) }

	directory { |relPath, create = true|
		var parts = this.components(relPath), path, type;
		this.resolve(relPath);
		parts.do { |part, index|
			path = this.resolve(parts.copyRange(0, index).join("/"));
			type = File.type(path);
			if(type == \not_found and: { create }) { File.mkdir(path); type = File.type(path) };
			if(type != \directory and: { create or: { type != \not_found } }) {
				MBProject.fail(\validation, "a project folder is not a directory: " ++ relPath.asString.quote)
			};
		};
		^this.resolve(relPath)
	}

	components { |relPath|
		var path, parts;
		if(relPath.isKindOf(Symbol)) { relPath = relPath.asString };
		if(relPath.isString.not) { MBProject.fail(\validation, "project paths must be strings") };
		path = relPath;
		if(path.isEmpty) { MBProject.fail(\validation, "empty project path") };
		if(path.size > maxPathSize) { MBProject.fail(\validation, "project path is too long") };
		if(path.any { |char| char.ascii >= 0 and: { char.ascii < 32 } }) {
			MBProject.fail(\validation, "project path contains control characters")
		};
		if(path.includes($\\) or: { path.includes($:) }) {
			MBProject.fail(\validation, "use forward-slash relative paths without drive letters: " ++ path.quote)
		};
		if(path[0] == $/ or: { path[0] == $~ }) {
			MBProject.fail(\validation, "path must be relative to the project: " ++ path.quote)
		};
		parts = path.split($/);
		if(parts.any { |part| part.isEmpty or: { part == "." } or: { part == ".." } }) {
			MBProject.fail(\validation, "path escapes or is not normalized within the project: " ++ path.quote)
		};
		^parts
	}

	// Containment checks compare paths with "/" separators; Windows paths
	// (File.realpath answers backslashes there) are also case-insensitive.
	*comparablePath { |path|
		path = path.asString.replace("\\", "/");
		^if(thisProcess.platform.name == \windows) { path.toLower } { path }
	}

	resolve { |relPath|
		var parts = this.components(relPath), current = root, type, real;
		if(File.type(root) != \directory) {
			MBProject.fail(\validation, "the project root is no longer a directory")
		};
		parts.do { |part, index|
			current = current +/+ part;
			type = File.type(current);
			if(type == \symlink) {
				MBProject.fail(\validation, "symbolic links are not allowed in project paths: " ++ relPath.asString.quote)
			};
			if(index < (parts.size - 1) and: { type != \not_found } and: { type != \directory }) {
				MBProject.fail(\validation, "a path component is not a folder: " ++ relPath.asString.quote)
			};
		};
		if(File.exists(current)) {
			real = File.realpath(current);
			if(real.isNil or: { MBProject.comparablePath(real).beginsWith(MBProject.comparablePath(root) ++ "/").not }) {
				MBProject.fail(\validation, "path resolves outside the project: " ++ relPath.asString.quote)
			};
		};
		^current
	}

	resolveEditable { |relPath|
		var parts = this.components(relPath), extension;
		if(parts.any { |part| part[0] == $. }) {
			MBProject.fail(\validation, "hidden files and the .maxxedbeats folder cannot be edited: " ++ relPath.quote)
		};
		if(parts[0].toLower == "renders") {
			MBProject.fail(\validation, "the renders folder cannot be edited: " ++ relPath.quote)
		};
		extension = parts.last.splitext[1];
		if(extension.isNil or: { editableExtensions.includesEqual(extension.toLower).not }) {
			MBProject.fail(\validation, "only " ++ editableExtensions.join("/") ++ " files can be edited: " ++ relPath.quote)
		};
		^this.resolve(relPath)
	}

	files {
		var result = List.new, walk;
		walk = { |dir, prefix, level|
			(dir +/+ "*").pathMatch.sort.do { |entry|
				var clean = entry.withoutTrailingSlash, name = clean.basename, type = File.type(clean);
				var rel = if(prefix.isEmpty) { name } { prefix ++ "/" ++ name };
				if(result.size < maxFiles and: { name[0] != $. }) {
					case
					{ type == \regular } { result.add(rel) }
					{ type == \directory and: { level < maxDepth } and: { rel.toLower != "renders" } } {
						walk.value(clean, rel, level + 1)
					};
				};
			};
		};
		walk.value(root, "", 0);
		^result.asArray
	}

	exists { |relPath| ^File.exists(this.resolve(relPath)) }

	read { |relPath|
		var path = this.resolve(relPath), size;
		if(File.exists(path).not) { MBProject.fail(\io, "file not found in project: " ++ relPath.asString.quote) };
		if(File.type(path) != \regular) { MBProject.fail(\validation, "not a regular file: " ++ relPath.asString.quote) };
		size = File.fileSize(path);
		if(size > maxFileBytes) {
			MBProject.fail(\validation, relPath.asString.quote ++ " is larger than " ++ maxFileBytes ++ " bytes")
		};
		^MBProject.readFile(path)
	}

	// spec: (path:, action: "create" | "replace" | "edit", oldText:, newText:)
	prepareEdit { |spec|
		var path, action, oldText, newText, absolute, exists, before, after, index;
		if(spec.isKindOf(Dictionary).not) { MBProject.fail(\validation, "each edit must be an object") };
		path = spec[\path] ? spec["path"];
		action = (spec[\action] ? spec["action"]).asString;
		oldText = spec[\oldText] ? spec["oldText"];
		newText = spec[\newText] ? spec["newText"];
		absolute = this.resolveEditable(path);
		path = path.asString;
		if(newText.isString.not) { MBProject.fail(\validation, "edit for " ++ path.quote ++ " needs newText") };
		if(newText.size > maxFileBytes) { MBProject.fail(\validation, "edit for " ++ path.quote ++ " is too large") };
		if(newText.includes(0.asAscii)) { MBProject.fail(\validation, "edit for " ++ path.quote ++ " contains NUL bytes") };
		exists = File.exists(absolute);
		if(exists and: { File.type(absolute) != \regular }) {
			MBProject.fail(\validation, path.quote ++ " is not a regular file")
		};
		^switch(action,
			"create", {
				if(exists) { MBProject.fail(\validation, path.quote ++ " already exists; use replace or edit") };
				if(oldText.notNil) { MBProject.fail(\validation, "create edits must not include oldText") };
				MBEdit(path, nil, newText, true, \create, nil, newText)
			},
			"replace", {
				if(exists.not) { MBProject.fail(\validation, path.quote ++ " does not exist; use create") };
				if(oldText.notNil) { MBProject.fail(\validation, "replace edits must not include oldText") };
				before = this.read(path);
				if(before == newText) { MBProject.fail(\validation, "edit for " ++ path.quote ++ " makes no change") };
				MBEdit(path, before, newText, false, \replace, before, newText)
			},
			"edit", {
				if(exists.not) { MBProject.fail(\validation, path.quote ++ " does not exist; use create") };
				if(oldText.isString.not or: { oldText.isEmpty }) {
					MBProject.fail(\validation, "edit for " ++ path.quote ++ " needs a non-empty oldText")
				};
				before = this.read(path);
				index = before.find(oldText);
				if(index.isNil) {
					MBProject.fail(\validation, "oldText was not found in " ++ path.quote)
				};
				if(before.find(oldText, offset: index + 1).notNil) {
					MBProject.fail(\validation, "oldText occurs more than once in " ++ path.quote ++ "; include more context")
				};
				after = before.copyRange(0, index - 1) ++ newText
					++ before.copyRange(index + oldText.size, before.size - 1);
				if(before == after) { MBProject.fail(\validation, "edit for " ++ path.quote ++ " makes no change") };
				MBEdit(path, oldText, newText, false, \edit, before, after)
			},
			{ MBProject.fail(\validation, "unknown edit action " ++ action.quote ++ "; use create, replace, or edit") }
		)
	}

	apply { |proposal, confirmed = false, onSuccess, onFailure|
		var outcome;
		if(confirmed !== true) {
			^this.prDeliver(onFailure, MBError(\validation,
				"edits were not applied: explicit confirmation is required after reviewing the diff"))
		};
		outcome = MBWorkflowTry.mbError({ this.prApply(proposal) }, \io);
		if(outcome.isKindOf(MBError)) { this.prDeliver(onFailure, outcome) } { this.prDeliver(onSuccess, outcome) };
	}

	backups {
		var dir = this.backupsDir;
		if(File.exists(dir).not) { ^[] };
		^(dir +/+ "*").pathMatch.collect(_.withoutTrailingSlash).sort.collect { |path|
			this.prReadManifest(path.basename)
		}.reject(_.isNil)
	}

	undo { |onSuccess, onFailure|
		var outcome = MBWorkflowTry.mbError({ this.prUndo }, \io);
		if(outcome.isKindOf(MBError)) { this.prDeliver(onFailure, outcome) } { this.prDeliver(onSuccess, outcome) };
	}

	prDeliver { |callback, value|
		AppClock.sched(0, { callback.value(value); nil });
	}

	prApply { |proposal|
		var edits, paths, id, dir, manifest, written = List.new, current, failure;
		if(proposal.isKindOf(Dictionary).not) { MBProject.fail(\validation, "apply needs a proposal") };
		edits = proposal[\edits];
		if(edits.isKindOf(SequenceableCollection).not or: { edits.isEmpty }) {
			MBProject.fail(\validation, "the proposal has no file edits to apply")
		};
		if(edits.any { |edit| edit.isKindOf(MBEdit).not }) {
			MBProject.fail(\validation, "the proposal contains an invalid edit")
		};
		paths = edits.collect(_.path);
		if(paths.collect(_.toLower).asSet.size != paths.size) { MBProject.fail(\validation, "the proposal edits a file more than once") };
		// Re-validate everything before touching the disk.
		edits.do { |edit|
			var absolute = this.resolveEditable(edit.path);
			current = if(File.exists(absolute)) { MBProject.readFile(absolute) } { nil };
			if(edit.isNew) {
				if(current.notNil) {
					MBProject.fail(\validation, edit.path.quote ++ " was created since the proposal; ask for a new proposal")
				}
			} {
				if(current != edit.before) {
					MBProject.fail(\validation, edit.path.quote ++ " changed since the proposal; review a new proposal before applying")
				}
			};
			if(edit.after.isString.not) { MBProject.fail(\validation, "edit for " ++ edit.path.quote ++ " has no contents") };
		};
		id = this.prNewBackupId;
		dir = this.directory(".maxxedbeats/backups/" ++ id);
		manifest = (
			format: "maxxedbeats.backup/1",
			id: id,
			createdAt: Date.getDate.format("%Y-%m-%dT%H:%M:%S"),
			summary: (proposal[\summary] ? "").asString.keep(500),
			undone: false,
			files: edits.collect { |edit| (path: edit.path, existed: edit.isNew.not) }
		);
		edits.do { |edit|
			if(edit.isNew.not) { MBProject.writeFile(dir +/+ "before" +/+ edit.path, edit.before) };
			MBProject.writeFile(dir +/+ "after" +/+ edit.path, edit.after);
		};
		MBProject.writeFile(dir +/+ "manifest.json", MBWorkflowJSON.stringify(manifest));
		failure = MBWorkflowTry.mbError({
			edits.do { |edit|
				var absolute = this.resolveEditable(edit.path);
				written.add(edit);
				MBProject.writeFile(absolute, edit.after);
			};
		}, \io);
		if(failure.isKindOf(MBError)) {
			written.do { |edit|
				var absolute = this.resolveEditable(edit.path);
				if(edit.isNew) {
					File.delete(absolute)
				} {
					MBWorkflowTry.value({ MBProject.writeFile(absolute, edit.before) })
				};
			};
			manifest[\undone] = true;
			MBWorkflowTry.value({ MBProject.writeFile(dir +/+ "manifest.json", MBWorkflowJSON.stringify(manifest)) });
			MBProject.fail(\io, "writing the edits failed and was rolled back: " ++ failure.detail);
		};
		^(backupId: id, paths: paths, summary: manifest[\summary])
	}

	prNewBackupId {
		var stamp = Date.getDate.format("%Y%m%d-%H%M%S"), id;
		this.directory(".maxxedbeats/backups");
		while {
			backupCounter = backupCounter + 1;
			id = stamp ++ "-" ++ backupCounter.asStringToBase(10, 3);
			File.exists(this.backupsDir +/+ id)
		};
		^id
	}

	prReadManifest { |id|
		var parsed = MBWorkflowTry.value({
			MBWorkflowJSON.parse(MBProject.readFile(this.backupsDir +/+ id +/+ "manifest.json"))
		});
		if(parsed.isKindOf(Dictionary).not or: { parsed["files"].isKindOf(Array).not }) { ^nil };
		^(
			id: id,
			createdAt: parsed["createdAt"],
			summary: parsed["summary"],
			undone: parsed["undone"] == true,
			files: parsed["files"],
			paths: parsed["files"].collect { |entry| entry["path"] }
		)
	}

	prUndo {
		var backup, dir, files, raw;
		backup = this.backups.reverse.detect { |entry| entry[\undone].not };
		if(backup.isNil) { MBProject.fail(\validation, "there is no applied edit to undo") };
		dir = this.backupsDir +/+ backup[\id];
		files = backup[\files].collect { |entry|
			var path = entry["path"], absolute = this.resolveEditable(path), expected, current;
			expected = MBProject.readFile(dir +/+ "after" +/+ path);
			current = if(File.exists(absolute)) { MBProject.readFile(absolute) } { nil };
			if(current != expected) {
				MBProject.fail(\validation, path.quote ++ " changed after the edit was applied; undo was refused "
					++ "so those changes are kept (the earlier version is in .maxxedbeats/backups/" ++ backup[\id] ++ ")")
			};
			(path: path, absolute: absolute, existed: entry["existed"] == true)
		};
		files.do { |entry|
			if(entry[\existed]) {
				MBProject.writeFile(entry[\absolute], MBProject.readFile(dir +/+ "before" +/+ entry[\path]))
			} {
				File.delete(entry[\absolute])
			};
		};
		raw = MBWorkflowJSON.parse(MBProject.readFile(dir +/+ "manifest.json"));
		raw["undone"] = true;
		raw["undoneAt"] = Date.getDate.format("%Y-%m-%dT%H:%M:%S");
		MBProject.writeFile(dir +/+ "manifest.json", MBWorkflowJSON.stringify(raw));
		^(backupId: backup[\id], paths: files.collect { |entry| entry[\path] })
	}
}
