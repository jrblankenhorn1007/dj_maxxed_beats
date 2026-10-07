/*
Cancellable handle for asynchronous workflow operations. cancel is
idempotent; onCancel functions run once.
*/
MBWorkflowHandle {
	var <cancelled = false, <finished = false, cancelActions;

	*new { ^super.new.initHandle }

	initHandle { cancelActions = List.new }

	onCancel { |function|
		if(cancelled) { function.value } { cancelActions.add(function) };
	}

	cancel {
		if(cancelled.not and: { finished.not }) {
			cancelled = true;
			cancelActions.do { |action| MBWorkflowTry.value(action) };
			cancelActions.clear;
		};
	}

	active { ^cancelled.not and: { finished.not } }

	finish { finished = true; cancelActions.clear }
}

/*
Turns a user prompt plus user-selected project context into a reviewable
proposal using the active provider and its explicitly selected model.

The system prompt is built only from agent/ROLE.md, WORKFLOW.md,
SUPERCOLLIDER.md, and SAFETY.md. Only files listed in context[\files] are
read (through MBProject confinement) and sent. propose never writes files,
evaluates code, or renders.
*/
MBAgent {
	classvar <>instructionsDir, <>maxContextBytes = 393216, <>maxContextFiles = 24, <>maxPromptBytes = 32768;
	classvar <instructionFiles = #["ROLE.md", "WORKFLOW.md", "SUPERCOLLIDER.md", "SAFETY.md"];
	var <project, <provider, <catalog, <meter;
	var <>maxOutputTokens = 16000, <>temperature;

	*new { |project, provider, catalog, meter|
		^super.newCopyArgs(project, provider, catalog, meter)
	}

	*findInstructionsDir {
		var classesDir, quarkRoot, candidates;
		if(instructionsDir.notNil) { ^instructionsDir };
		classesDir = this.filenameSymbol.asString.dirname.dirname;
		quarkRoot = classesDir.dirname;
		candidates = [quarkRoot +/+ "agent", quarkRoot.dirname +/+ "agent"];
		^candidates.detect { |dir| File.exists(dir +/+ instructionFiles[0]) } ? candidates[0]
	}

	*systemPrompt {
		var dir = this.findInstructionsDir, sections;
		sections = instructionFiles.collect { |name|
			var path = dir +/+ name, text;
			if(File.exists(path).not) {
				MBError(\config, "agent instructions are missing: " ++ name ++ " (expected in " ++ dir ++ ")").throw
			};
			text = MBProject.readFile(path).stripWhiteSpace;
			if(text.isEmpty) { MBError(\config, "agent instruction file is empty: " ++ name).throw };
			"<!-- agent/" ++ name ++ " -->\n" ++ text
		};
		^sections.join("\n\n")
	}

	*fence { |text|
		var longest = 0, run = 0;
		text.do { |char|
			if(char == $`) { run = run + 1; longest = max(longest, run) } { run = 0 };
		};
		^String.fill(max(3, longest + 1), $`)
	}

	selectedModel {
		var model = catalog !? { catalog.selectedModel(provider.id) };
		if(model.isKindOf(Symbol)) { model = model.asString };
		if(model.isString.not or: { model.isEmpty }) {
			MBError(\config, "choose a model for " ++ (provider.tryPerform(\displayName) ? provider.id).asString
				++ " before sending a prompt").throw
		};
		^model
	}

	// context: (files: [relPath], notes: String, history: [(role:, content:)],
	// entry: relPath, seed: Float, variation: (index:, count:))
	buildRequest { |userPrompt, context|
		var files, history, content, totalBytes = 0, stream, messages, notes, model;
		context = context ? ();
		if(userPrompt.isString.not or: { userPrompt.stripWhiteSpace.isEmpty }) {
			MBError(\validation, "describe what you want the DJ to do").throw
		};
		if(userPrompt.size > maxPromptBytes) { MBError(\validation, "the prompt is too long").throw };
		model = this.selectedModel;
		files = (context[\files] ? []).asArray;
		if(files.size > maxContextFiles) {
			MBError(\validation, "select at most " ++ maxContextFiles ++ " project files as context").throw
		};
		stream = CollStream.on(String.new);
		stream.putAll("## Request\n\n" ++ userPrompt.stripWhiteSpace ++ "\n");
		if(files.notEmpty) {
			stream.putAll("\n## Selected project context\n\nThe user selected these project files. Paths are relative "
				++ "to the project root; propose edits only with these relative paths or new files.\n");
			files.do { |path|
				var text = project.read(path), fence, ending;
				totalBytes = totalBytes + text.size;
				if(totalBytes > maxContextBytes) {
					MBError(\validation, "the selected context is larger than " ++ maxContextBytes ++ " bytes; select fewer files").throw
				};
				fence = MBAgent.fence(text);
				ending = if(text.endsWith("\n")) { "" } { "\n" };
				stream.putAll("\n### File: " ++ path.asString ++ "\n\n" ++ fence ++ "supercollider\n" ++ text
					++ ending ++ fence ++ "\n");
			};
		};
		context[\entry] !? { |entry|
			project.resolve(entry);
			stream.putAll("\n## Composition to render\n\n" ++ entry.asString ++ "\n");
		};
		notes = context[\notes];
		if(notes.notNil) {
			if(notes.isString.not or: { notes.size > maxPromptBytes }) { MBError(\validation, "notes must be short text").throw };
			stream.putAll("\n## Notes from the user and the workflow\n\n" ++ notes ++ "\n");
		};
		context[\seed] !? { |seed|
			stream.putAll("\n## Required seed\n\nUse seed " ++ MBResponseFormat.seedValue(seed)
				++ " (read it from ~mbRender[\\seed]) and report it in \"seed\".\n");
		};
		context[\variation] !? { |variation|
			stream.putAll("\n## Variation\n\nThis is candidate " ++ variation[\index] ++ " of " ++ variation[\count]
				++ " in a user-started sampling session. Make it a distinct musical alternative.\n");
		};
		stream.putAll("\n## Response\n\nReply with exactly one JSON object in the " ++ MBResponseFormat.formatId
			++ " format from your instructions, with no other text.\n");
		history = (context[\history] ? []).asArray.collect { |message|
			var role = message[\role] !? { |r| r.asSymbol };
			if([\user, \assistant].includes(role).not or: { message[\content].isString.not }) {
				MBError(\validation, "conversation history may only contain user and assistant text").throw
			};
			totalBytes = totalBytes + message[\content].size;
			(role: role, content: message[\content])
		};
		if(totalBytes > maxContextBytes) { MBError(\validation, "the conversation history is too long").throw };
		messages = history ++ [(role: \user, content: stream.contents)];
		^(
			model: model,
			system: MBAgent.systemPrompt,
			messages: messages,
			maxOutputTokens: maxOutputTokens,
			temperature: temperature
		)
	}

	propose { |userPrompt, context, onSuccess, onFailure|
		var handle = MBWorkflowHandle.new, request, deliver, providerHandle;
		deliver = { |callback, value|
			if(handle.active) {
				handle.finish;
				AppClock.sched(0, { callback.value(value); nil });
			}
		};
		handle.onCancel {
			providerHandle !? { MBWorkflowTry.value({ providerHandle.cancel }) };
			AppClock.sched(0, { onFailure.value(MBError(\cancelled, "the request was cancelled")); nil });
		};
		request = MBWorkflowTry.mbError({ this.buildRequest(userPrompt, context) }, \validation);
		if(request.isKindOf(MBError)) {
			deliver.value(onFailure, request);
			^handle
		};
		providerHandle = provider.complete(request,
			{ |response|
				var usage, proposal;
				if(handle.active) {
					usage = meter !? { MBWorkflowTry.value({ meter.record(response) }) };
					if(usage.isKindOf(Error)) { usage = nil };
					proposal = MBWorkflowTry.mbError({ MBResponseFormat.parse(response[\text], project) }, \parse);
					if(proposal.isKindOf(MBError)) {
						deliver.value(onFailure, proposal)
					} {
						proposal.putAll((
							usage: usage,
							raw: response[\text],
							provider: response[\provider] ? provider.id,
							model: response[\model] ? request[\model],
							requestId: response[\requestId],
							prompt: userPrompt
						));
						deliver.value(onSuccess, proposal)
					}
				}
			},
			{ |error|
				deliver.value(onFailure, if(error.isKindOf(MBError)) { error } {
					MBError(\server, "the provider request failed")
				})
			}
		);
		^handle
	}
}
