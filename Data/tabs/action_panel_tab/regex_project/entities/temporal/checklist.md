# Temporal Entities Checklist

- [x] `\b(\d{1,2}:\d{2}(?:\s?[ap]m)?)\b` (Time: 12:00 or 12:00 pm)
- [x] `\b(\d{1,2}/\d{1,2}/\d{2,4})\b` (Date: MM/DD/YYYY or DD/MM/YY)
- [x] `\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?` (Full Date: January 25th)
- [x] `\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b` (Days of the week)
- [x] `\b(today|tomorrow|yesterday)\b` (Relative days)
- [x] `\b(in|within)\s+(\d+|a|an)\s+(minute|hour|day|week|month|year)s?\b` (Future durations)
- [x] `\b(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago\b` (Past durations)
- [x] `\b(morning|afternoon|evening|night)\b` (Times of day)
- [x] `\b(now|soon|later|immediately)\b` (Temporal adverbs)
- [x] `\b(\d{4})\b` (Year detection)
