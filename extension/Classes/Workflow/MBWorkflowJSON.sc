/*
Strict JSON for the MaxxedBeats workflow layer.

MBWorkflowJSON.parse(string) follows RFC 8259: one value, no comments, no
trailing commas, no duplicate object keys, depth-limited. Objects become
Dictionaries with String keys (null members are omitted); arrays become
Arrays; null becomes nil. Errors are MBError(\parse) and never echo input.
MBWorkflowJSON.stringify(value) writes objects with sorted keys.
*/
MBWorkflowJSON {
	classvar <>maxDepth = 32;

	*parse { |string|
		if(string.isString.not) {
			MBError(\parse, "expected JSON text but got " ++ string.class.name).throw
		};
		^MBWorkflowJSONParser.new(string, maxDepth).parseDocument
	}

	*stringify { |value, pretty = true|
		var stream = CollStream.on(String.new);
		this.prWrite(value, stream, 0, pretty);
		^stream.contents
	}

	*quote { |string|
		var stream = CollStream.on(String.new);
		this.prWriteString(string.asString, stream);
		^stream.contents
	}

	*prWrite { |value, stream, level, pretty|
		var newline, indent, inner, keys, first;
		newline = if(pretty) { "\n" } { "" };
		indent = if(pretty) { String.fill(level * 2, Char.space) } { "" };
		inner = if(pretty) { String.fill((level + 1) * 2, Char.space) } { "" };
		case
		{ value.isNil } { stream.putAll("null") }
		{ value === true } { stream.putAll("true") }
		{ value === false } { stream.putAll("false") }
		{ value.isKindOf(Symbol) } { this.prWriteString(value.asString, stream) }
		{ value.isString } { this.prWriteString(value, stream) }
		{ value.isKindOf(Integer) } { stream.putAll(value.asString) }
		{ value.isKindOf(SimpleNumber) } {
			if(value.isNaN or: { value.abs == inf }) {
				stream.putAll("null")
			} {
				stream.putAll(value.asFloat.asString)
			}
		}
		{ value.isKindOf(Dictionary) } {
			keys = value.keys.asArray.collect(_.asString).sort;
			if(keys.isEmpty) { stream.putAll("{}") } {
				stream.putAll("{" ++ newline);
				first = true;
				keys.do { |key|
					var member = value[key];
					if(member.isNil) { member = value[key.asSymbol] };
					if(first.not) { stream.putAll("," ++ newline) };
					first = false;
					stream.putAll(inner);
					this.prWriteString(key, stream);
					stream.putAll(if(pretty) { ": " } { ":" });
					this.prWrite(member, stream, level + 1, pretty);
				};
				stream.putAll(newline ++ indent ++ "}");
			}
		}
		{ value.isKindOf(SequenceableCollection) } {
			if(value.isEmpty) { stream.putAll("[]") } {
				stream.putAll("[" ++ newline);
				value.do { |item, index|
					if(index > 0) { stream.putAll("," ++ newline) };
					stream.putAll(inner);
					this.prWrite(item, stream, level + 1, pretty);
				};
				stream.putAll(newline ++ indent ++ "]");
			}
		}
		{ value.isKindOf(Boolean) } { stream.putAll(value.asString) }
		{ MBError(\validation, "cannot encode a " ++ value.class.name ++ " as JSON").throw };
	}

	*prWriteString { |string, stream|
		var start = 0, flush;
		flush = { |end| if(end > start) { stream.putAll(string.copyRange(start, end - 1)) } };
		stream.put($");
		string.do { |char, index|
			var code = char.ascii, escape;
			escape = case
			{ char == $" } { "\\\"" }
			{ char == $\\ } { "\\\\" }
			{ code == 10 } { "\\n" }
			{ code == 13 } { "\\r" }
			{ code == 9 } { "\\t" }
			{ code >= 0 and: { code < 32 } or: { code == 127 } } {
				"\\u" ++ code.asHexString(4).toLower
			}
			{ nil };
			if(escape.notNil) {
				flush.value(index);
				stream.putAll(escape);
				start = index + 1;
			};
		};
		flush.value(string.size);
		stream.put($");
	}
}

MBWorkflowJSONParser {
	var source, position, size, depth, maxDepth;

	*new { |string, maxDepth = 32|
		^super.new.initParser(string, maxDepth)
	}

	initParser { |string, argMaxDepth|
		source = string;
		position = 0;
		size = string.size;
		depth = 0;
		maxDepth = argMaxDepth;
	}

	fail { |message|
		MBError(\parse, "invalid JSON at character " ++ position ++ ": " ++ message).throw
	}

	peek { ^if(position < size) { source[position] } { nil } }

	expect { |char|
		if(this.peek != char) { this.fail("expected '" ++ char ++ "'") };
		position = position + 1;
	}

	skipWhitespace {
		var char;
		while {
			position < size and: {
				char = source[position];
				char == Char.space or: { char == $\n } or: { char == $\r } or: { char == $\t }
			}
		} {
			position = position + 1
		};
	}

	parseDocument {
		var value;
		this.skipWhitespace;
		value = this.parseValue;
		this.skipWhitespace;
		if(position < size) { this.fail("unexpected content after the JSON value") };
		^value
	}

	parseValue {
		var char;
		if(position >= size) { this.fail("unexpected end of input") };
		char = source[position];
		^case
		{ char == ${ } { this.parseObject }
		{ char == $[ } { this.parseArray }
		{ char == $" } { this.parseString }
		{ char == $t } { this.parseLiteral("true", true) }
		{ char == $f } { this.parseLiteral("false", false) }
		{ char == $n } { this.parseLiteral("null", nil) }
		{ char == $- or: { char.isDecDigit } } { this.parseNumber }
		{ this.fail("unexpected character") }
	}

	enter {
		depth = depth + 1;
		if(depth > maxDepth) { this.fail("nesting deeper than " ++ maxDepth) };
	}

	parseObject {
		var result = Dictionary.new, seen = Set.new, key, value, done = false;
		this.enter;
		position = position + 1;
		this.skipWhitespace;
		if(this.peek == $}) {
			position = position + 1;
			done = true;
		};
		while { done.not } {
			this.skipWhitespace;
			if(this.peek != $") { this.fail("expected a string object key") };
			key = this.parseString;
			if(seen.includes(key)) { this.fail("duplicate object key \"" ++ key.keep(40) ++ "\"") };
			seen.add(key);
			this.skipWhitespace;
			this.expect($:);
			this.skipWhitespace;
			value = this.parseValue;
			if(value.notNil) { result.put(key, value) };
			this.skipWhitespace;
			if(this.peek == $,) {
				position = position + 1;
			} {
				this.expect($});
				done = true;
			};
		};
		depth = depth - 1;
		^result
	}

	parseArray {
		var result = Array.new(8), done = false;
		this.enter;
		position = position + 1;
		this.skipWhitespace;
		if(this.peek == $]) {
			position = position + 1;
			done = true;
		};
		while { done.not } {
			this.skipWhitespace;
			result = result.add(this.parseValue);
			this.skipWhitespace;
			if(this.peek == $,) {
				position = position + 1;
			} {
				this.expect($]);
				done = true;
			};
		};
		depth = depth - 1;
		^result
	}

	parseLiteral { |text, value|
		if(position + text.size > size or: {
			source.copyRange(position, position + text.size - 1) != text
		}) {
			this.fail("invalid literal")
		};
		position = position + text.size;
		^value
	}

	parseNumber {
		var start = position, isInteger = true, text, value, digits;
		digits = {
			var first = position;
			while { position < size and: { source[position].isDecDigit } } { position = position + 1 };
			if(position == first) { this.fail("expected a digit") };
		};
		if(this.peek == $-) { position = position + 1 };
		if(this.peek == $0) {
			position = position + 1;
			if(this.peek.notNil and: { this.peek.isDecDigit }) { this.fail("leading zeros are not allowed") };
		} {
			digits.value;
		};
		if(this.peek == $.) {
			isInteger = false;
			position = position + 1;
			digits.value;
		};
		if(this.peek == $e or: { this.peek == $E }) {
			isInteger = false;
			position = position + 1;
			if(this.peek == $+ or: { this.peek == $- }) { position = position + 1 };
			digits.value;
		};
		text = source.copyRange(start, position - 1);
		if(isInteger and: { text.size < 10 }) { ^text.asInteger };
		value = text.asFloat;
		if(value.isNaN or: { value.abs == inf }) { this.fail("number out of range") };
		^value
	}

	parseHex4 {
		var value = 0, char;
		4.do {
			char = this.peek;
			if(char.isNil or: { "0123456789abcdefABCDEF".includes(char).not }) {
				this.fail("invalid \\u escape")
			};
			value = (value * 16) + char.digit;
			position = position + 1;
		};
		^value
	}

	putCodePoint { |stream, code|
		case
		{ code < 128 } { stream.put(code.asAscii) }
		{ code < 2048 } {
			stream.put((192 + (code >> 6)).asAscii);
			stream.put((128 + (code & 63)).asAscii);
		}
		{ code < 65536 } {
			stream.put((224 + (code >> 12)).asAscii);
			stream.put((128 + ((code >> 6) & 63)).asAscii);
			stream.put((128 + (code & 63)).asAscii);
		}
		{
			stream.put((240 + (code >> 18)).asAscii);
			stream.put((128 + ((code >> 12) & 63)).asAscii);
			stream.put((128 + ((code >> 6) & 63)).asAscii);
			stream.put((128 + (code & 63)).asAscii);
		};
	}

	parseString {
		var stream = CollStream.on(String.new), start, char, code, low, done = false;
		position = position + 1;
		start = position;
		while { done.not } {
			if(position >= size) { this.fail("unterminated string") };
			char = source[position];
			case
			{ char == $" } {
				if(position > start) { stream.putAll(source.copyRange(start, position - 1)) };
				position = position + 1;
				done = true;
			}
			{ char == $\\ } {
				if(position > start) { stream.putAll(source.copyRange(start, position - 1)) };
				position = position + 1;
				char = this.peek;
				position = position + 1;
				case
				{ char == $" } { stream.put($") }
				{ char == $\\ } { stream.put($\\) }
				{ char == $/ } { stream.put($/) }
				{ char == $b } { stream.put(8.asAscii) }
				{ char == $f } { stream.put(12.asAscii) }
				{ char == $n } { stream.put($\n) }
				{ char == $r } { stream.put($\r) }
				{ char == $t } { stream.put($\t) }
				{ char == $u } {
					code = this.parseHex4;
					if(code >= 16rDC00 and: { code <= 16rDFFF }) { this.fail("unpaired surrogate") };
					if(code >= 16rD800 and: { code <= 16rDBFF }) {
						if(this.peek != $\\) { this.fail("unpaired surrogate") };
						position = position + 1;
						if(this.peek != $u) { this.fail("unpaired surrogate") };
						position = position + 1;
						low = this.parseHex4;
						if(low < 16rDC00 or: { low > 16rDFFF }) { this.fail("unpaired surrogate") };
						code = 16r10000 + ((code - 16rD800) << 10) + (low - 16rDC00);
					};
					if(code == 0) { this.fail("NUL characters are not allowed") };
					this.putCodePoint(stream, code);
				}
				{ this.fail("invalid escape sequence") };
				start = position;
			}
			{ code = char.ascii; code >= 0 and: { code < 32 } } {
				this.fail("unescaped control character in string")
			}
			{ position = position + 1 };
		};
		^stream.contents
	}
}
