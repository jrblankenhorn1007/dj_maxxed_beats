// HTTPS transport: the OS curl binary run asynchronously through MBProcess.
//
// The API key never enters process arguments, the environment, or files.
// The credential store supplies a shell prelude that reads the key into an
// unexported shell variable (from the OS store, or from a private FIFO for
// the in-memory test store); a shell builtin (printf) pipes a one-line curl
// config ("header = ...") to `curl -K -`. `-q` disables ~/.curlrc so user
// configuration cannot add tracing. TLS verification stays on (no -k);
// plain http is accepted only for loopback test servers.
MBHttp {
	classvar <>curlPath = "curl";

	*isLoopback { |url|
		^#["http://127.0.0.1:", "http://127.0.0.1/", "http://localhost:", "http://localhost/",
			"http://[::1]:", "http://[::1]/"].any { |prefix| url.beginsWith(prefix) }
	}

	*checkUrl { |url|
		if(url.isString.not) { ^MBError(\config, "Provider base URL is missing") };
		if(url.beginsWith("https://") or: { this.isLoopback(url) }) { ^nil };
		^MBError(\config, "Provider base URL must use https:// (plain http is only allowed "
			++ "for a loopback test server): " ++ MBRedact.string(url))
	}

	// request: (method:, url:, headers: [String], body: String or nil,
	//   timeout:, connectTimeout:, auth: (store:, id:, header: "Authorization: Bearer ") or nil)
	// onComplete.(result): (status:, headers: Dictionary, body:, error: MBError or nil)
	*request { |request, onComplete|
		var dir, error, script, auth = request[\auth], payload, process, handle;
		handle = MBRequestHandle.new;
		error = this.checkUrl(request[\url]);
		if(error.notNil) {
			{ if(handle.finish) { onComplete.value((error: error)) } }.defer;
			^handle
		};
		dir = MBProviderPaths.newRunDir;
		if(request[\body].notNil) {
			error = MBProviderPaths.writeText(dir +/+ "request.json", request[\body]);
		};
		if(error.notNil) {
			MBProviderPaths.removeDir(dir);
			{ if(handle.finish) { onComplete.value((error: error)) } }.defer;
			^handle
		};
		if(auth.notNil) { payload = auth[\store].keyPayload(auth[\id]) };
		script = if(MBProviderPaths.isWindows) {
			this.windowsScript(request, dir)
		} {
			this.posixScript(request, dir)
		};
		process = MBProcess.run(script, dir, payload,
			(request[\timeout] ? 120) + 10,
			{ |code, why|
				var result = this.prResult(code, why, dir, request);
				MBProviderPaths.removeDir(dir);
				if(handle.finish) { onComplete.value(result) };
			});
		handle.inner = process;
		^handle
	}

	*curlArgs { |request, quote|
		var args = List.new, timeout = request[\timeout] ? 120;
		args.add("-q").add("-sS").add("-g");
		args.add("--proto").add(if(this.isLoopback(request[\url])) { "=http,https" } { "=https" });
		args.add("--max-time").add(timeout.asString);
		args.add("--connect-timeout").add((request[\connectTimeout] ? 15).asString);
		args.add("--max-filesize").add("33554432");
		args.add("-X").add(request[\method] ? "GET");
		(request[\headers] ? []).do { |header| args.add("-H").add(header) };
		if(request[\body].notNil) { args.add("--data-binary").add("@request.json") };
		args.add("-D").add("response-headers.txt");
		args.add("-o").add("response-body.txt");
		if(request[\auth].notNil) { args.add("-K").add("-") };
		args.add(request[\url]);
		^args.collect { |item| quote.(item) }.join(" ")
	}

	*posixScript { |request, dir|
		var auth = request[\auth], lines = List.new, curl;
		curl = curlPath.shellQuote ++ " " ++ this.curlArgs(request, _.shellQuote)
			++ " 2> curl-stderr.txt";
		lines.add("umask 077");
		lines.add("cd " ++ dir.shellQuote ++ " || exit 123");
		lines.add("command -v " ++ curlPath.shellQuote ++ " >/dev/null 2>&1 || exit 122");
		if(auth.isNil) {
			lines.add(curl);
		} {
			lines.add(auth[\store].keyPrelude(auth[\id], "@FIFO@"));
			lines.add("case \"$key\" in ''|*[!A-Za-z0-9_.-]*) exit 121 ;; esac");
			lines.add("printf 'header = \"%s%s\"\\n' " ++ auth[\header].shellQuote
				++ " \"$key\" | " ++ curl);
		};
		^lines.join("\n")
	}

	*windowsScript { |request, dir|
		// Not runtime-verified (no Windows host); see docs/design/providers.md.
		var auth = request[\auth], quote, curl;
		quote = { |text| "\"" ++ text.asString.replace("\"", "\\\"") ++ "\"" };
		curl = "curl.exe " ++ this.curlArgs(request, quote) ++ " 2> curl-stderr.txt";
		if(auth.notNil) {
			curl = auth[\store].keyPrelude(auth[\id], nil, auth[\header]) ++ " | " ++ curl;
		};
		^"cd /d " ++ quote.(dir) ++ " && " ++ curl
	}

	*prResult { |code, why, dir, request|
		var headerText, headers, status, stderr;
		if(why == \cancelled) {
			^(error: MBError(\cancelled, "Request cancelled"))
		};
		if(why == \timeout) {
			^(error: MBError(\network, "Request timed out after "
				++ (request[\timeout] ? 120) ++ " s"))
		};
		stderr = MBRedact.string(MBProviderPaths.readText(dir +/+ "curl-stderr.txt").stripWhiteSpace);
		if(code != 0) { ^(error: this.curlError(code, stderr, request)) };
		headerText = MBProviderPaths.readText(dir +/+ "response-headers.txt");
		#status, headers = this.parseHeaders(headerText);
		if(status.isNil) { ^(error: MBError(\network, "No HTTP response received")) };
		^(status: status, headers: headers,
			body: MBProviderPaths.readText(dir +/+ "response-body.txt"), error: nil)
	}

	*parseHeaders { |text|
		var status, headers = Dictionary.new;
		text.split($\n).do { |line|
			var colon;
			line = line.stripWhiteSpace;
			if(line.beginsWith("HTTP/")) {
				status = line.split($ )[1].asInteger;
				headers = Dictionary.new;
			} {
				colon = line.find(":");
				if(colon.notNil and: { colon > 0 }) {
					headers[line.keep(colon).toLower] = line.drop(colon + 1).stripWhiteSpace;
				}
			}
		};
		^[status, headers]
	}

	*curlError { |code, stderr, request|
		var tls = #[35, 51, 53, 54, 58, 59, 60, 64, 66, 77, 80, 82, 83, 90, 91];
		^case
		{ code == 120 } { MBError(\auth, "No API key is stored for this provider") }
		{ code == 121 } { MBError(\auth, "The stored API key is empty or malformed; replace it") }
		{ code == 122 or: { code == 127 } } {
			MBError(\config, "The curl command was not found; it ships with macOS, "
				++ "Windows 10+, and most Linux distributions")
		}
		{ code == 123 } { MBError(\io, "Could not use the private request directory") }
		{ code == 28 } {
			MBError(\network, "Request timed out after " ++ (request[\timeout] ? 120) ++ " s")
		}
		{ code == 6 } { MBError(\network, "Could not resolve the provider host") }
		{ code == 7 } { MBError(\network, "Could not connect to the provider") }
		{ code == 63 } { MBError(\network, "Provider response exceeded the size limit") }
		{ tls.includes(code) } {
			MBError(\network, "TLS/certificate verification failed (curl " ++ code ++ "): " ++ stderr)
		}
		{ code == 143 or: { code == 15 } } { MBError(\cancelled, "Request cancelled") }
		{ MBError(\network, "Transport failed (curl exit " ++ code ++ "): " ++ stderr) }
	}
}
