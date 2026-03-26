# Negative Constraints Checklist

- [x] `\b(not|n't)\s+hello\b` (Negated greeting)
- [x] `\b(don't|do not)\s+agree\b` (Negated agreement -> Disagreement)
- [x] `\b(?i)test\b` (Ignore test strings)
- [x] `\b(if|unless)\b.*?\?` (Conditional questions - different strategy)
- [x] `\b(maybe|might|could be)\b` (Filter out weak affirmations)
- [x] `\b(just)\s+(a|an)\s+\w+\b` (Distinguish "just" as quantifier vs hedge)
- [x] `\b(like)\b` (Distinguish "like" as verb vs hesitation filler)
- [x] `\b(well)\b` (Distinguish "well" as adverb vs hesitation filler)
- [x] `\b(so)\b` (Distinguish "so" as conjunction vs intensifier)
- [x] `\b(that's|it's)\b\s+(not)\b` (Catching negated semantics)
