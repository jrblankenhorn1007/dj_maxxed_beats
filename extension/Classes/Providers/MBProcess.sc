// Runs one helper process (curl, security, secret-tool, powershell)
// asynchronously and reports its exit exactly once on AppClock:
// onExit.(exitCode, reason) with reason \exited, \timeout, or \cancelled.
//
// A secret payload is never put in process arguments, the environment, or a
// file: on POSIX it is written into a private named pipe (FIFO, no data at
// rest) that the child reads as stdin ("@FIFO@" in the script).
MBProcess {
	var <pid, <dir, onExit, <finished = false, <reason, watchdog;

	*run { |script, dir, payload, timeout, onExit|
		^super.new.prInit(dir, onExit).prRun(script, payload, timeout)
	}

	prInit { |argDir, argOnExit|
		dir = argDir;
		onExit = argOnExit;
	}

	prRun { |script, payload, timeout|
		if(MBProviderPaths.isWindows) {
			^this.prRunWindows(script, payload, timeout)
		};
		^this.prRunPosix(script, payload, timeout)
	}

	prRunPosix { |script, payload, timeout|
		var fifo, file;
		if(payload.notNil) {
			fifo = dir +/+ "secret.fifo";
			("umask 077; mkfifo -m 600 " ++ fifo.shellQuote).systemCmd;
			script = script.replace("@FIFO@", fifo.shellQuote);
		};
		pid = ["/bin/sh", "-c", script].unixCmd({ |code| this.prExited(code) }, false);
		if(payload.notNil) {
			if(pid.isNil or: { pid <= 0 }) {
				File.delete(fifo);
			} {
				// If the child died before opening the FIFO, this guard opens
				// it after a few seconds so the language never waits forever.
				["/bin/sh", "-c", "sleep 3; [ -p " ++ fifo.shellQuote ++ " ] && exec 3<>"
					++ fifo.shellQuote ++ " && sleep 2"].unixCmd(nil, false);
				file = File(fifo, "w");
				File.delete(fifo);
				if(file.isOpen) {
					file.write(payload);
					file.close;
				};
			};
		};
		this.prStartWatchdog(timeout);
	}

	prRunWindows { |script, payload, timeout|
		var pipe, code;
		if(payload.notNil) {
			// Not runtime-verified on Windows (see docs/design/providers.md):
			// stdin delivery through Pipe; close waits for the short-lived
			// credential helper to exit.
			pipe = Pipe(script, "w");
			pipe.putString(payload);
			code = pipe.close;
			{ this.prExited(code) }.defer;
			^this
		};
		pid = script.unixCmd({ |exitCode| this.prExited(exitCode) }, false);
		this.prStartWatchdog(timeout);
	}

	prStartWatchdog { |timeout|
		if(timeout.notNil) {
			watchdog = Routine {
				timeout.wait;
				if(finished.not) { this.prKill; this.prFinish(nil, \timeout) };
			}.play(AppClock);
		};
	}

	prExited { |code|
		{ this.prFinish(code, \exited) }.defer;
	}

	prFinish { |code, why|
		if(finished) { ^this };
		finished = true;
		reason = why;
		watchdog !? { watchdog.stop };
		onExit.value(code, why);
	}

	prKill {
		if(pid.isNil) { ^this };
		if(MBProviderPaths.isWindows) {
			("taskkill /PID " ++ pid ++ " /T /F").unixCmd(nil, false)
		} {
			("pkill -TERM -P " ++ pid ++ " ; kill -TERM " ++ pid ++ " 2>/dev/null")
				.unixCmd(nil, false)
		}
	}

	cancel {
		if(finished) { ^this };
		this.prKill;
		this.prFinish(nil, \cancelled);
	}
}

// Handle returned by provider requests. Responds to .cancel; cancelling
// reports MBError(\cancelled) to onFailure once and suppresses later results.
MBRequestHandle {
	var <isDone = false, <isCancelled = false, <>inner, onCancel;

	*new { |onCancel| ^super.new.prInit(onCancel) }

	prInit { |argOnCancel| onCancel = argOnCancel }

	cancel {
		if(isDone) { ^this };
		isCancelled = true;
		isDone = true;
		inner !? { inner.cancel };
		onCancel.value;
	}

	// Returns true if the caller may deliver a result (first finisher wins).
	finish {
		if(isDone) { ^false };
		isDone = true;
		^true
	}
}
