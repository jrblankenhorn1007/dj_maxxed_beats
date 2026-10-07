/*
Exception capture that is safe on SuperCollider 3.14.1.

A plain `try` corrupts the caller's pending message sends when the caught
error was raised while arguments were being evaluated (for example
`list.add(this.mayThrow)` under the try): the interpreter later skips or
misroutes an unrelated call. Running the guarded function on its own
Routine stack keeps the caller intact. The function must not yield or wait.

MBWorkflowTry.value(function) returns the function's result, or the caught
Error. MBWorkflowTry.mbError(function, kind) converts a caught non-MBError
into MBError(kind, ...).
*/
MBWorkflowTry {
	*value { |function|
		var outcome;
		Routine {
			outcome = try { function.value } { |error| error };
			nil
		}.next;
		^outcome
	}

	*mbError { |function, kind = \io|
		var outcome = this.value(function);
		if(outcome.isKindOf(Error) and: { outcome.isKindOf(MBError).not }) {
			outcome = MBError(kind, outcome.errorString)
		};
		^outcome
	}
}
