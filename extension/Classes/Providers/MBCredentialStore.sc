// API-key storage in the operating system's credential store.
//
//   MBCredentialStore.default -> platform backend (macOS Keychain, Windows
//                                Credential Manager, Linux Secret Service)
//   MBCredentialStore.fake    -> in-memory store for tests
//
// Keys are passed to backends only through stdin/FIFO, never through
// process arguments, environment variables, files, or messages. Keys are
// never returned to the language: requests read them inside the transport
// pipeline (see MBHttp). All callbacks run on AppClock.
MBCredentialStore {
	classvar <serviceName = "MaxxedBeats", <providerIds, default;

	*initClass { providerIds = #[\openai, \anthropic] }

	*default {
		^default ?? {
			default = switch(thisProcess.platform.name,
				\osx, { MBKeychainCredentialStore.new },
				\windows, { MBWindowsCredentialStore.new },
				{ MBSecretServiceCredentialStore.new })
		}
	}

	*fake { ^MBFakeCredentialStore.new }

	*displayNameFor { |id|
		^switch(id.asSymbol, \openai, "OpenAI", \anthropic, "Anthropic (Claude)", id.asString)
	}

	*checkId { |id|
		if(id.isNil or: { providerIds.includes(id.asSymbol).not }) {
			^MBError(\config, "Unknown provider for API keys: " ++ id.asString
				++ " (expected openai or anthropic)")
		};
		^nil
	}

	// Provider API keys are opaque tokens; restricting the alphabet keeps
	// them safe inside backend command streams and curl config lines.
	*checkKey { |id, key|
		var error = this.checkId(id);
		if(error.notNil) { ^error };
		if(key.isString.not or: { key.size < 8 } or: { key.size > 512 }) {
			^MBError(\validation, "The " ++ this.displayNameFor(id)
				++ " API key must be 8-512 characters")
		};
		if(key.every { |char| char.isAlphaNum or: { "_.-".includes(char) } }.not
			or: { key[0].isAlphaNum.not }) {
			^MBError(\validation, "The " ++ this.displayNameFor(id)
				++ " API key contains unsupported characters (spaces, quotes, or line breaks?)")
		};
		^nil
	}

	account { |id| ^id.asString }
	label { |id| ^serviceName ++ " " ++ this.class.displayNameFor(id) ++ " API key" }

	hasKey { |id, onResult|
		var error = this.class.checkId(id);
		if(error.notNil) { { onResult.value(false) }.defer; ^this };
		this.prRun(this.hasCommand(id), nil, { |code| onResult.value(code == 0) });
	}

	storeKey { |id, key, onSuccess, onFailure|
		var error = this.class.checkKey(id, key);
		if(error.notNil) { { onFailure.value(error) }.defer; ^this };
		this.prRun(this.storeCommand(id, "@FIFO@"), this.storePayload(id, key),
			{ |code, stderr|
				if(code == 0) { onSuccess.value } {
					onFailure.value(this.backendError("store", code, MBRedact.string(stderr, [key])))
				}
			});
	}

	removeKey { |id, onSuccess, onFailure|
		var error = this.class.checkId(id);
		if(error.notNil) { { onFailure.value(error) }.defer; ^this };
		this.prRun(this.removeCommand(id), nil, { |code, stderr|
			if(this.removeSucceeded(code)) { onSuccess.value } {
				onFailure.value(this.backendError("remove", code, MBRedact.string(stderr)))
			}
		});
	}

	// Confirms the stored key works by listing models (a non-billable call).
	validateKey { |id, onSuccess, onFailure, provider|
		var error = this.class.checkId(id);
		if(error.notNil) { { onFailure.value(error) }.defer; ^this };
		provider = provider ?? { MBProviderRegistry.new(this).at(id) };
		this.hasKey(id, { |present|
			if(present.not) {
				onFailure.value(MBError(\auth, "No API key is stored for "
					++ this.class.displayNameFor(id)))
			} {
				provider.listModels(onSuccess, onFailure)
			}
		});
	}

	removeSucceeded { |code| ^code == 0 }

	backendError { |operation, code, detail|
		if(code == 127) {
			^MBError(\config, this.backendName ++ " is not available: " ++ this.missingToolHint)
		};
		^MBError(\io, "Could not " ++ operation ++ " the API key in " ++ this.backendName
			++ " (exit " ++ code ++ ")" ++ if(detail.size > 0) { ": " ++ detail } { "" })
	}

	backendName { ^"the credential store" }
	missingToolHint { ^"" }

	// Subclass hooks (shell command text must never contain the key).
	keyPrelude { |id, fifo| ^this.subclassResponsibility(thisMethod) }
	keyPayload { |id| ^nil }
	hasCommand { |id| ^this.subclassResponsibility(thisMethod) }
	storeCommand { |id, fifo| ^this.subclassResponsibility(thisMethod) }
	storePayload { |id, key| ^key }
	removeCommand { |id| ^this.subclassResponsibility(thisMethod) }

	prRun { |command, payload, action|
		var dir = MBProviderPaths.newRunDir, script;
		script = if(MBProviderPaths.isWindows) { command } {
			"umask 077\ncd " ++ dir.shellQuote ++ " || exit 123\n" ++ command
		};
		MBProcess.run(script, dir, payload, 60, { |code, why|
			var stderr = MBProviderPaths.readText(dir +/+ "stderr.txt").stripWhiteSpace;
			MBProviderPaths.removeDir(dir);
			action.value(if(why == \exited) { code } { -1 }, stderr);
		});
	}

	printOn { |stream| stream << this.class.name << "(" << this.backendName << ")" }
}

// macOS: the `security` tool. Writes go through `security -i` reading the
// command from a FIFO so the key is never an argument of any process.
MBKeychainCredentialStore : MBCredentialStore {
	var <keychain;

	*new { |keychain| ^super.new.prInitKeychain(keychain) }

	prInitKeychain { |path| keychain = path }

	backendName { ^"the macOS Keychain" }

	keychainArg { ^if(keychain.isNil) { "" } { " " ++ keychain.shellQuote } }

	itemArgs { |id|
		^"-s " ++ serviceName.shellQuote ++ " -a " ++ this.account(id).shellQuote
	}

	keyPrelude { |id, fifo|
		^"key=$(/usr/bin/security find-generic-password " ++ this.itemArgs(id) ++ " -w"
			++ this.keychainArg ++ " 2>/dev/null) || exit 120"
	}

	hasCommand { |id|
		^"/usr/bin/security find-generic-password " ++ this.itemArgs(id) ++ this.keychainArg
			++ " >/dev/null 2>&1"
	}

	storeCommand { |id, fifo|
		^"/usr/bin/security -i < " ++ fifo ++ " >/dev/null 2> stderr.txt"
	}

	storePayload { |id, key|
		var quote = { |text| "\"" ++ text ++ "\"" };
		^"add-generic-password -U -s " ++ quote.(serviceName) ++ " -a " ++ quote.(this.account(id))
			++ " -l " ++ quote.(this.label(id)) ++ " -w " ++ key
			++ if(keychain.isNil) { "" } { " " ++ quote.(keychain) } ++ "\n"
	}

	removeCommand { |id|
		^"/usr/bin/security delete-generic-password " ++ this.itemArgs(id) ++ this.keychainArg
			++ " >/dev/null 2> stderr.txt"
	}

	// 44 = errSecItemNotFound: removing an absent key is not a failure.
	removeSucceeded { |code| ^code == 0 or: { code == 44 } }
}

// Linux: libsecret's `secret-tool` (Secret Service, e.g. GNOME Keyring or
// KWallet). The key is read from stdin by `secret-tool store`.
MBSecretServiceCredentialStore : MBCredentialStore {
	backendName { ^"the Secret Service keyring" }
	missingToolHint { ^"install libsecret-tools (secret-tool) and a keyring daemon" }

	attributes { |id|
		^"service " ++ serviceName.shellQuote ++ " account " ++ this.account(id).shellQuote
	}

	keyPrelude { |id, fifo|
		^"key=$(secret-tool lookup " ++ this.attributes(id) ++ " 2>/dev/null) || exit 120"
	}

	hasCommand { |id|
		^"secret-tool lookup " ++ this.attributes(id) ++ " >/dev/null 2>&1"
	}

	storeCommand { |id, fifo|
		^"secret-tool store --label=" ++ this.label(id).shellQuote ++ " "
			++ this.attributes(id) ++ " < " ++ fifo ++ " 2> stderr.txt"
	}

	removeCommand { |id|
		^"secret-tool clear " ++ this.attributes(id) ++ " 2> stderr.txt"
	}
}

// Windows: Credential Manager through the bundled PowerShell helper
// Data/windows/MaxxedBeatsCredential.ps1 (CredRead/CredWrite/CredDelete).
// Designed for Windows 10+, but not runtime-verified on a Windows host yet.
MBWindowsCredentialStore : MBCredentialStore {
	backendName { ^"Windows Credential Manager" }

	helper {
		var path = MBProviderPaths.dataDir +/+ "windows" +/+ "MaxxedBeatsCredential.ps1";
		^"powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \""
			++ path ++ "\""
	}

	keyPrelude { |id, fifo, header|
		^this.helper ++ " curlconfig " ++ this.account(id) ++ " \""
			++ (header ? "Authorization: Bearer ") ++ "\""
	}

	hasCommand { |id| ^this.helper ++ " has " ++ this.account(id) }

	storeCommand { |id, fifo| ^this.helper ++ " store " ++ this.account(id) }

	removeCommand { |id| ^this.helper ++ " remove " ++ this.account(id) }
}

// In-memory store for tests and demos. Keys stay in this object; requests
// receive them through a private FIFO like the production store commands.
MBFakeCredentialStore : MBCredentialStore {
	var keys;

	*new { ^super.new.prInitFake }

	prInitFake { keys = IdentityDictionary.new }

	backendName { ^"fake in-memory store" }

	hasKey { |id, onResult|
		var present = this.class.checkId(id).isNil and: { keys[id.asSymbol].notNil };
		{ onResult.value(present) }.defer;
	}

	storeKey { |id, key, onSuccess, onFailure|
		var error = this.class.checkKey(id, key);
		if(error.notNil) { { onFailure.value(error) }.defer; ^this };
		keys[id.asSymbol] = key.copy;
		{ onSuccess.value }.defer;
	}

	removeKey { |id, onSuccess, onFailure|
		var error = this.class.checkId(id);
		if(error.notNil) { { onFailure.value(error) }.defer; ^this };
		keys.removeAt(id.asSymbol);
		{ onSuccess.value }.defer;
	}

	keyPrelude { |id, fifo|
		if(keys[id.asSymbol].isNil) { ^"exit 120" };
		^"key=$(cat " ++ fifo ++ ") || exit 120"
	}

	keyPayload { |id| ^keys[id.asSymbol] }

	hasCommand { |id| ^"true" }
	storeCommand { |id, fifo| ^"cat " ++ fifo ++ " >/dev/null" }
	removeCommand { |id| ^"true" }
}
