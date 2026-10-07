MBError : Error {
	var <kind, <detail;

	*new { |kind = \config, detail = ""|
		^super.new(detail.asString).initMBError(kind, detail)
	}

	initMBError { |argKind, argDetail|
		kind = argKind.asSymbol;
		detail = argDetail.asString;
	}

	errorString {
		^"MaxxedBeats " ++ kind.asString ++ " error: " ++ detail
	}
}
