/*
A single reviewable file edit inside an MBProject.

kind: \create (new file; oldText nil), \replace (whole file; oldText is the
previous contents) or \edit (oldText occurs exactly once and is replaced by
newText). before/after are the complete file contents at proposal time;
MBProject.apply refuses to write if the file no longer matches before.
*/
MBEdit {
	var <path, <oldText, <newText, <isNew, <kind, <before, <after;

	*new { |path, oldText, newText, isNew = false, kind = \edit, before, after|
		^super.newCopyArgs(path, oldText, newText, isNew, kind, before, after)
	}

	diffString { ^MBDiff.unified(before, after, path, isNew) }

	asMetadata {
		^(path: path, action: kind.asString, isNew: isNew, diff: this.diffString)
	}

	printOn { |stream|
		stream << "MBEdit(" << kind << ", " << path << ")"
	}
}

/*
Line-based unified diff (3 lines of context) for reviewing edits. Common
prefix/suffix lines are trimmed first; the middle uses an LCS table when
small enough and otherwise a single replace hunk.
*/
MBDiff {
	classvar <>maxTableCells = 1000000;

	*lines { |text|
		var result = Array.new(64), start = 0;
		if(text.isNil or: { text.isEmpty }) { ^[] };
		text.do { |char, index|
			if(char == $\n) {
				result = result.add(text.copyRange(start, index - 1));
				start = index + 1;
			};
		};
		if(start < text.size) { result = result.add(text.copyRange(start, text.size - 1)) };
		^result
	}

	*operations { |a, b|
		var prefix = 0, suffix = 0, ops, middleA, middleB, table, i, j, n, m;
		while { prefix < a.size and: { prefix < b.size } and: { a[prefix] == b[prefix] } } {
			prefix = prefix + 1
		};
		while {
			suffix < (a.size - prefix) and: { suffix < (b.size - prefix) }
			and: { a[a.size - 1 - suffix] == b[b.size - 1 - suffix] }
		} {
			suffix = suffix + 1
		};
		ops = Array.new(a.size + b.size);
		prefix.do { |k| ops = ops.add([\equal, a[k]]) };
		middleA = a.copyRange(prefix, a.size - suffix - 1);
		middleB = b.copyRange(prefix, b.size - suffix - 1);
		n = middleA.size;
		m = middleB.size;
		if((n * m) > 0 and: { (n * m) <= maxTableCells }) {
			table = Array.fill(n + 1, { Int32Array.newClear(m + 1) });
			(n - 1).forBy(0, -1) { |x|
				(m - 1).forBy(0, -1) { |y|
					table[x][y] = if(middleA[x] == middleB[y]) {
						table[x + 1][y + 1] + 1
					} {
						max(table[x + 1][y], table[x][y + 1])
					}
				}
			};
			i = 0;
			j = 0;
			while { i < n and: { j < m } } {
				case
				{ middleA[i] == middleB[j] } { ops = ops.add([\equal, middleA[i]]); i = i + 1; j = j + 1 }
				{ table[i + 1][j] >= table[i][j + 1] } { ops = ops.add([\delete, middleA[i]]); i = i + 1 }
				{ ops = ops.add([\insert, middleB[j]]); j = j + 1 };
			};
			while { i < n } { ops = ops.add([\delete, middleA[i]]); i = i + 1 };
			while { j < m } { ops = ops.add([\insert, middleB[j]]); j = j + 1 };
		} {
			middleA.do { |line| ops = ops.add([\delete, line]) };
			middleB.do { |line| ops = ops.add([\insert, line]) };
		};
		(a.size - suffix).for(a.size - 1) { |k| ops = ops.add([\equal, a[k]]) };
		^ops
	}

	*unified { |oldText, newText, path, isNew = false, context = 3|
		var a, b, ops, changes, stream, groups, current, oldLine, newLine, positions;
		a = this.lines(oldText);
		b = this.lines(newText);
		stream = CollStream.on(String.new);
		stream.putAll(if(isNew) { "--- /dev/null\n" } { "--- a/" ++ path ++ "\n" });
		stream.putAll("+++ b/" ++ path ++ "\n");
		ops = this.operations(a, b);
		// positions[k] = [old line index, new line index] before op k
		positions = Array.new(ops.size);
		oldLine = 0;
		newLine = 0;
		ops.do { |op|
			positions = positions.add([oldLine, newLine]);
			if(op[0] != \insert) { oldLine = oldLine + 1 };
			if(op[0] != \delete) { newLine = newLine + 1 };
		};
		changes = ops.collect { |op, k| if(op[0] != \equal) { k } }.reject(_.isNil);
		if(changes.isEmpty) {
			if(oldText != newText) {
				stream.putAll("(only the trailing newline changed)\n")
			} {
				stream.putAll("(no changes)\n")
			};
			^stream.contents
		};
		groups = List.new;
		current = [changes[0], changes[0]];
		changes.drop(1).do { |k|
			if(k - current[1] <= (2 * context + 1)) { current[1] = k } {
				groups.add(current);
				current = [k, k];
			}
		};
		groups.add(current);
		groups.do { |group|
			var first = max(0, group[0] - context), last = min(ops.size - 1, group[1] + context);
			var oldCount = 0, newCount = 0, oldStart, newStart;
			first.for(last) { |k|
				if(ops[k][0] != \insert) { oldCount = oldCount + 1 };
				if(ops[k][0] != \delete) { newCount = newCount + 1 };
			};
			oldStart = positions[first][0] + if(oldCount > 0) { 1 } { 0 };
			newStart = positions[first][1] + if(newCount > 0) { 1 } { 0 };
			stream.putAll("@@ -" ++ oldStart ++ "," ++ oldCount ++ " +" ++ newStart ++ "," ++ newCount ++ " @@\n");
			first.for(last) { |k|
				var prefix = switch(ops[k][0], \equal, " ", \delete, "-", \insert, "+");
				stream.putAll(prefix ++ ops[k][1] ++ "\n");
			};
		};
		^stream.contents
	}
}
