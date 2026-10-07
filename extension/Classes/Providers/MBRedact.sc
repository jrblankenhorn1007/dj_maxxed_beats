// Removes API-key-shaped tokens, auth header values, and caller-supplied
// secrets from any text before it reaches an MBError, the post window, or a
// file. Detail is also length-limited.
MBRedact {
	classvar <patterns, <>maxLength = 400;

	*initClass {
		patterns = [
			"sk-[A-Za-z0-9_*.\\-]{6,}",
			"(?i)bearer\\s+[^\\s\"',;]+",
			"(?i)(?:x-api-key|authorization|api[-_ ]?key)\\s*[:=]\\s*[^\\s\"',;]+",
			"(?i)(?:x-api-key|api[-_ ]?key|token)\\s+[A-Za-z0-9_\\-]{16,}"
		];
	}

	*string { |text, secrets|
		var ranges = List.new, result, cursor = 0, merged = List.new;
		text = (text ? "").asString;
		patterns.do { |pattern|
			text.findRegexp(pattern).do { |match|
				ranges.add([match[0], match[0] + match[1].size - 1])
			}
		};
		secrets.do { |secret|
			var from = 0, index;
			secret = secret.asString;
			if(secret.size >= 4) {
				while { (index = text.find(secret, offset: from)).notNil } {
					ranges.add([index, index + secret.size - 1]);
					from = index + secret.size;
				}
			}
		};
		ranges.asArray.sort { |a, b| a[0] <= b[0] }.do { |range|
			if(merged.notEmpty and: { range[0] <= (merged.last[1] + 1) }) {
				merged.last[1] = max(merged.last[1], range[1])
			} {
				merged.add(range.copy)
			}
		};
		result = CollStream(String.new);
		merged.do { |range|
			if(range[0] > cursor) { result << text.copyRange(cursor, range[0] - 1) };
			result << "[REDACTED]";
			cursor = range[1] + 1;
		};
		if(cursor < text.size) { result << text.copyRange(cursor, text.size - 1) };
		result = result.contents;
		if(result.size > maxLength) { result = result.keep(maxLength) ++ "..." };
		^result
	}
}
