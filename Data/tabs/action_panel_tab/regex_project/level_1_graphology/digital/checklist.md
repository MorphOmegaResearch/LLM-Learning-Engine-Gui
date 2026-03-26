# Digital Graphology Checklist

- [x] `https?://\S+` (URL detection)
- [x] `[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}` (Email detection)
- [x] `#\w+` (Hashtag detection)
- [x] `@\w+` (Mention/Handle detection)
- [x] `\b\d{1,3}(\.\d{1,3}){3}\b` (IP Address detection)
- [x] `[:;=]-?[)D(|\]]` (Emoticon detection)
- [x] `[^\x00-\x7F]+` (Non-ASCII/Emoji placeholder detection)
- [x] `\b[A-Z0-9]{5,}\b` (Serial/Product key potential)
- [x] `\w+/\w+` (Path/Slash-separated units)
- [x] `\.{3}` (Ellipsis detection)
