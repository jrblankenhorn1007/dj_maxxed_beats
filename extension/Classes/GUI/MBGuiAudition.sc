// Optional live preview of a rendered file on the user's own server, and
// "Reveal in file browser". Playback never boots the server, never evaluates
// generated code, and plays a file the renderer already produced.

MBGuiAudition {
	var <path, <server, buffer, synth, onDone, stopped = false;

	*play { |path, onStarted, onDone, onFailure, server|
		server = server ? Server.default;
		if(path.isNil or: { File.exists(path.asString).not }) {
			onFailure.value(MBError(\io, "Rendered file not found: " ++ path));
			^nil
		};
		if(server.serverRunning.not) {
			onFailure.value(MBError(\config,
				"The audio server is not running. Boot it with s.boot, then press Play again "
				++ "(playback is an optional preview; the WAV file is already rendered)."));
			^nil
		};
		^super.new.init(path.asString, server, onStarted, onDone, onFailure)
	}

	*reveal { |path|
		var dir;
		if(path.isNil) { ^nil };
		path = path.asString;
		dir = if(File.exists(path) and: { File.type(path) != \directory }) { path.dirname } { path };
		^Platform.case(
			\osx, { ["open", "-R", path].unixCmd(postOutput: false) },
			\windows, { ["explorer", "/select," ++ path.replace("/", "\\")].unixCmd(postOutput: false) },
			{ ["xdg-open", dir].unixCmd(postOutput: false) }
		)
	}

	init { |argPath, argServer, onStarted, argOnDone, onFailure|
		path = argPath;
		server = argServer;
		onDone = argOnDone;
		Buffer.read(server, path, action: { |buf|
			{
				if(stopped) {
					buf.free;
				} {
					if(buf.numFrames.isNil or: { buf.numFrames < 1 }) {
						buf.free;
						onFailure.value(MBError(\io, "The server could not read " ++ path));
					} {
						buffer = buf;
						synth = {
							var sig = PlayBuf.ar(buf.numChannels, buf.bufnum,
								BufRateScale.kr(buf.bufnum), doneAction: 2);
							Limiter.ar(if(buf.numChannels == 1) { sig ! 2 } { sig }, 0.95)
						}.play(server);
						synth.onFree { { this.finish }.defer };
						onStarted.value(this);
					};
				};
			}.defer;
		});
	}

	stop {
		stopped = true;
		if(synth.notNil) { synth.free } { this.finish };
	}

	finish {
		if(buffer.notNil) { buffer.free; buffer = nil };
		synth = nil;
		if(onDone.notNil) { onDone.value(this); onDone = nil };
	}
}
