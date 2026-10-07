// Runs one helper process (curl, security, secret-tool, powershell)
// asynchronously and reports its exit exactly once on AppClock:
// onExit.(exitCode, reason) with reason \exited, \timeout, or \cancelled.
//
// A secret payload is never put in process arguments, the environment, or a
// file. On POSIX the script is run by /bin/sh and the payload is written into
// a private named pipe (FIFO, no data at rest) that the child reads as stdin
// ("@FIFO@" in the script). On Windows the script is an argv Array (the
// MaxxedBeatsCredential.ps1 helper) started with Pipe.argv, so the payload
// line goes straight to the helper's stdin; the helper writes its exit code
// to <dir>/exit-code.txt last, which is polled on AppClock.
MBProcess {
	classvar <>pollInterval = 0.05;
	var <pid, <dir, onExit, <finished = false, <reason, watchdog, pipe, poller;

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

	prRunWindows { |argv, payload, timeout|
		var exitFile = dir +/+ "exit-code.txt";
		argv = argv.collect { |item| if(item == "@RUNDIR@") { dir } { item } };
		pipe = Pipe.argv(argv, "w");
		if(pipe.isOpen.not) {
			pipe = nil;
			{ this.prFinish(127, \exited) }.defer;
			^this
		};
		pid = pipe.mbPid;
		// Always one line: the key, or an empty line when the helper does not
		// read stdin (it then stays unread in the pipe buffer).
		pipe.putString((payload ? "") ++ "\n");
		pipe.flush;
		poller = Routine {
			while { finished.not } {
				pollInterval.wait;
				if(finished.not and: { File.exists(exitFile) }) {
					this.prFinish(MBProviderPaths.readText(exitFile).stripWhiteSpace.asInteger, \exited);
				};
			};
		}.play(AppClock);
		this.prStartWatchdog(timeout);
	}

	// Pipe.close waits for the process; only close once it has surely ended.
	prReleaseWindowsPipe { |kill|
		var finishedPipe = pipe, finishedPid = pid;
		pipe = nil;
		if(finishedPipe.isNil) { ^this };
		AppClock.sched(if(kill) { 1 } { 2 }, {
			MBProviderPaths.killTree(finishedPid);
			AppClock.sched(1, { finishedPipe.close; nil });
			nil
		});
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
		poller !? { poller.stop };
		if(MBProviderPaths.isWindows) { this.prReleaseWindowsPipe(why != \exited) };
		onExit.value(code, why);
	}

	prKill {
		if(pid.isNil) { ^this };
		if(MBProviderPaths.isWindows) {
			MBProviderPaths.killTree(pid)
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

// Pipe keeps the child's process id private; MBProcess needs it to stop the
// helper's process tree on Windows.
+ Pipe {
	mbPid { ^pid }
}
