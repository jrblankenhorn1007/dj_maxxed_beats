// Masked API-key entry. The TextField draws its text transparently and is
// emptied on every keystroke/paste, so the key is never drawn: characters
// move into an in-memory buffer and only a count of asterisks is shown.
// Only appending, Backspace, and Clear are supported (no mid-key editing).

MBMaskedField {
	var <field, <display, secret, <>onChange;

	*new { ^super.new.init }

	init {
		secret = "";
		field = TextField()
			.stringColor_(Color.clear)
			.toolTip_("Paste or type the API key; it is never shown.");
		field.keyDownAction = { |view, char, modifiers, unicode|
			if(unicode == 8 or: { unicode == 127 }) {
				this.backspace;
				true
			} {
				// Let Qt insert typed/pasted text, then move it into the buffer.
				{ this.sync }.defer(0);
				nil
			}
		};
		field.action = { this.sync };
		field.focusLostAction = { this.sync };
		display = StaticText().string_("");
		this.updateDisplay;
	}

	sync {
		var typed;
		if(field.isNil or: { field.isClosed }) { ^this };
		typed = field.string;
		if(typed.size > 0) {
			secret = secret ++ typed.reject { |char| char == $\n or: { char == $\r } };
			field.string = "";
			this.changedSecret;
		};
	}

	backspace {
		if(secret.size > 0) {
			secret = secret.copyRange(0, secret.size - 2);
			this.changedSecret;
		};
	}

	clear {
		secret = "";
		if(field.notNil and: { field.isClosed.not }) { field.string = "" };
		this.changedSecret;
	}

	// The only accessor of the entered key; used when the user presses Save.
	secret {
		this.sync;
		^secret.copy
	}

	isEmpty { ^secret.size == 0 }

	changedSecret {
		this.updateDisplay;
		onChange.value(this);
	}

	updateDisplay {
		if(display.isNil or: { display.isClosed }) { ^this };
		display.string = if(secret.size == 0) { "(no key entered)" } {
			String.fill(secret.size.min(12), $*) ++ " (" ++ secret.size ++ " chars)"
		};
	}
}
