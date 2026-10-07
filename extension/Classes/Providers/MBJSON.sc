// Strict JSON (RFC 8259) parser and encoder for provider payloads.
// Objects parse to Dictionary with String keys, null to nil, true/false to
// Booleans, integers that fit 32 bits to Integer and other numbers to Float.
// Malformed input throws MBError(\parse).
MBJSON {
	*parse { |text|
		^MBJSONParser(text.asString).parseDocument
	}

	*encode { |object|
		var stream = CollStream(String.new);
		this.prEncode(object, stream);
		^stream.contents
	}

	*prEncode { |object, stream|
		case
		{ object.isNil } { stream << "null" }
		{ object === true } { stream << "true" }
		{ object === false } { stream << "false" }
		{ object.isKindOf(Integer) } { stream << object.asString }
		{ object.isKindOf(Float) } {
			if(object.isNaN or: { object.abs == inf }) {
				stream << "null"
			} {
				stream << this.prFloatString(object)
			}
		}
		{ object.isKindOf(String) or: { object.isKindOf(Symbol) } } {
			this.prEncodeString(object.asString, stream)
		}
		{ object.isKindOf(Dictionary) } {
			var keys = object.keys.asArray.collect(_.asString).sort;
			var lookup = Dictionary.new;
			object.keysValuesDo { |key, value| lookup[key.asString] = value };
			stream << "{";
			keys.do { |key, index|
				if(index > 0) { stream << "," };
				this.prEncodeString(key, stream);
				stream << ":";
				this.prEncode(lookup[key], stream);
			};
			stream << "}";
		}
		{ object.isKindOf(SequenceableCollection) } {
			stream << "[";
			object.do { |item, index|
				if(index > 0) { stream << "," };
				this.prEncode(item, stream);
			};
			stream << "]";
		}
		{ this.prEncodeString(object.asString, stream) };
	}

	*prFloatString { |value|
		^value.asStringPrec(17)
	}

	*prEncodeString { |string, stream|
		stream << $";
		string.do { |char|
			var code = char.ascii;
			case
			{ char == $" } { stream << "\\\"" }
			{ char == $\\ } { stream << "\\\\" }
			{ code == 10 } { stream << "\\n" }
			{ code == 13 } { stream << "\\r" }
			{ code == 9 } { stream << "\\t" }
			{ code == 8 } { stream << "\\b" }
			{ code == 12 } { stream << "\\f" }
			{ code >= 0 and: { code < 32 } or: { code == 127 } } {
				stream << "\\u" << code.asHexString(4).toLower
			}
			{ stream << char };
		};
		stream << $";
	}
}

MBJSONParser {
	var text, pos, size;

	*new { |text| ^super.new.init(text) }

	init { |argText|
		text = argText;
		pos = 0;
		size = text.size;
	}

	fail { |message|
		MBError(\parse, "Malformed JSON at byte " ++ pos ++ ": " ++ message).throw
	}

	parseDocument {
		var value;
		this.skipSpace;
		if(pos >= size) { this.fail("empty document") };
		value = this.parseValue;
		this.skipSpace;
		if(pos < size) { this.fail("unexpected trailing data") };
		^value
	}

	skipSpace {
		while { pos < size and: { [32, 9, 10, 13].includes(text[pos].ascii) } } {
			pos = pos + 1
		}
	}

	expectWord { |word, value|
		if(text.copyRange(pos, pos + word.size - 1) == word) {
			pos = pos + word.size;
			^value
		};
		this.fail("invalid literal");
	}

	parseValue {
		var char;
		if(pos >= size) { this.fail("unexpected end of input") };
		char = text[pos];
		^case
		{ char == ${ } { this.parseObject }
		{ char == $[ } { this.parseArray }
		{ char == $" } { this.parseString }
		{ char == $t } { this.expectWord("true", true) }
		{ char == $f } { this.expectWord("false", false) }
		{ char == $n } { this.expectWord("null", nil) }
		{ char == $- or: { char.isDecDigit } } { this.parseNumber }
		{ this.fail("unexpected character") }
	}

	parseObject {
		var dict = Dictionary.new, key, value;
		pos = pos + 1;
		this.skipSpace;
		if(pos < size and: { text[pos] == $} }) { pos = pos + 1; ^dict };
		loop {
			this.skipSpace;
			if(pos >= size or: { text[pos] != $" }) { this.fail("expected object key") };
			key = this.parseString;
			this.skipSpace;
			if(pos >= size or: { text[pos] != $: }) { this.fail("expected ':'") };
			pos = pos + 1;
			this.skipSpace;
			// Separate statements: an exception thrown while call arguments are
			// pending corrupts later calls in sclang 3.14 Routines.
			value = this.parseValue;
			dict.put(key, value);
			this.skipSpace;
			if(pos >= size) { this.fail("unterminated object") };
			if(text[pos] == $}) { pos = pos + 1; ^dict };
			if(text[pos] != $,) { this.fail("expected ',' or '}'") };
			pos = pos + 1;
		}
	}

	parseArray {
		var array = Array.new, value;
		pos = pos + 1;
		this.skipSpace;
		if(pos < size and: { text[pos] == $] }) { pos = pos + 1; ^array };
		loop {
			this.skipSpace;
			value = this.parseValue;
			array = array.add(value);
			this.skipSpace;
			if(pos >= size) { this.fail("unterminated array") };
			if(text[pos] == $]) { pos = pos + 1; ^array };
			if(text[pos] != $,) { this.fail("expected ',' or ']'") };
			pos = pos + 1;
		}
	}

	parseHex4 {
		var value = 0, digit;
		if(pos + 4 > size) { this.fail("truncated \\u escape") };
		4.do {
			if(text[pos].isAlphaNum.not) { this.fail("invalid \\u escape") };
			digit = text[pos].digit;
			if(digit > 15) { this.fail("invalid \\u escape") };
			value = value * 16 + digit;
			pos = pos + 1;
		};
		^value
	}

	utf8 { |code|
		var bytes = case
		{ code < 0x80 } { [code] }
		{ code < 0x800 } { [0xC0 | (code >> 6), 0x80 | (code & 0x3F)] }
		{ code < 0x10000 } {
			[0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)]
		}
		{
			[0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F),
				0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)]
		};
		^String.newFrom(bytes.collect(_.asAscii))
	}

	parseString {
		var pieces = Array.new, start, char, code, low;
		pos = pos + 1;
		start = pos;
		loop {
			if(pos >= size) { this.fail("unterminated string") };
			char = text[pos];
			code = char.ascii;
			case
			{ char == $" } {
				pieces = pieces.add(text.copyRange(start, pos - 1));
				pos = pos + 1;
				^pieces.join
			}
			{ char == $\\ } {
				pieces = pieces.add(text.copyRange(start, pos - 1));
				pos = pos + 1;
				if(pos >= size) { this.fail("unterminated escape") };
				char = text[pos];
				pos = pos + 1;
				case
				{ char == $" } { pieces = pieces.add("\"") }
				{ char == $\\ } { pieces = pieces.add("\\") }
				{ char == $/ } { pieces = pieces.add("/") }
				{ char == $b } { pieces = pieces.add(8.asAscii.asString) }
				{ char == $f } { pieces = pieces.add(12.asAscii.asString) }
				{ char == $n } { pieces = pieces.add("\n") }
				{ char == $r } { pieces = pieces.add("\r") }
				{ char == $t } { pieces = pieces.add("\t") }
				{ char == $u } {
					code = this.parseHex4;
					if(code >= 0xD800 and: { code < 0xDC00 }) {
						if(pos + 1 < size and: { text[pos] == $\\ } and: { text[pos + 1] == $u }) {
							pos = pos + 2;
							low = this.parseHex4;
							if(low < 0xDC00 or: { low > 0xDFFF }) { this.fail("invalid surrogate pair") };
							code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00);
						} {
							this.fail("unpaired surrogate")
						}
					} {
						if(code >= 0xDC00 and: { code <= 0xDFFF }) { this.fail("unpaired surrogate") }
					};
					pieces = pieces.add(this.utf8(code));
				}
				{ this.fail("invalid escape") };
				start = pos;
			}
			{ code >= 0 and: { code < 32 } } { this.fail("control character in string") }
			{ pos = pos + 1 };
		}
	}

	parseNumber {
		var start = pos, token, isFloat = false, digits;
		if(text[pos] == $-) { pos = pos + 1 };
		if(pos >= size or: { text[pos].isDecDigit.not }) { this.fail("invalid number") };
		if(text[pos] == $0) {
			pos = pos + 1;
			if(pos < size and: { text[pos].isDecDigit }) { this.fail("leading zero") };
		} {
			while { pos < size and: { text[pos].isDecDigit } } { pos = pos + 1 };
		};
		if(pos < size and: { text[pos] == $. }) {
			isFloat = true;
			pos = pos + 1;
			if(pos >= size or: { text[pos].isDecDigit.not }) { this.fail("invalid fraction") };
			while { pos < size and: { text[pos].isDecDigit } } { pos = pos + 1 };
		};
		if(pos < size and: { text[pos] == $e or: { text[pos] == $E } }) {
			isFloat = true;
			pos = pos + 1;
			if(pos < size and: { text[pos] == $+ or: { text[pos] == $- } }) { pos = pos + 1 };
			if(pos >= size or: { text[pos].isDecDigit.not }) { this.fail("invalid exponent") };
			while { pos < size and: { text[pos].isDecDigit } } { pos = pos + 1 };
		};
		token = text.copyRange(start, pos - 1);
		digits = token.count(_.isDecDigit);
		if(isFloat or: { digits > 9 }) { ^token.asFloat };
		^token.asInteger
	}
}
