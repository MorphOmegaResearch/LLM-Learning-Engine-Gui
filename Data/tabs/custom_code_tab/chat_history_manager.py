# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Chat History Manager - Save and load conversation histories
Manages persistent storage of chat conversations for each model
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class ChatHistoryManager:
    """Manages saving and loading chat conversation histories"""

    def __init__(self, history_dir: Optional[Path] = None):
        """
        Initialize the chat history manager

        Args:
            history_dir: Directory to store chat histories (default: Training_Data-Sets/ChatHistories)
        """
        if history_dir is None:
            self.history_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "ChatHistories"
        else:
            self.history_dir = Path(history_dir)

        # Ensure history directory exists
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Index file for quick lookups
        self.index_file = self.history_dir / "chat_index.json"

    def save_conversation(
        self,
        model_name: str,
        chat_history: List[Dict[str, Any]],
        session_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save a conversation history

        Args:
            model_name: Name of the model used
            chat_history: List of message dicts with role and content
            session_name: Optional custom name for this session
            metadata: Optional metadata (timestamp, tags, etc.)

        Returns:
            Session ID (filename stem)
        """
        try:
            # Generate session ID if not provided
            if session_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_name = f"{model_name}_{timestamp}"
            else:
                # Clean session name
                session_name = "".join(c for c in session_name if c.isalnum() or c in ('_', '-', ' '))
                session_name = session_name.replace(' ', '_')

            # Create conversation record
            conversation_record = {
                "session_id": session_name,
                "model_name": model_name,
                "chat_history": chat_history,
                "message_count": len(chat_history),
                "saved_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            # Save to file
            session_file = self.history_dir / f"{session_name}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_record, f, indent=2)

            # Update index
            self._update_index(session_name, model_name, len(chat_history))

            return session_name

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to save conversation: {e}")
            return ""

    def load_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation by session ID

        Args:
            session_id: Session ID to load

        Returns:
            Conversation record dict or None if not found
        """
        try:
            session_file = self.history_dir / f"{session_id}.json"
            if not session_file.exists():
                return None

            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to load conversation: {e}")
            return None

    def list_conversations(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all saved conversations

        Args:
            model_name: Filter by specific model (None for all)

        Returns:
            List of conversation summary dicts
        """
        try:
            conversations = []

            for session_file in self.history_dir.glob("*.json"):
                if session_file.stem == "chat_index":
                    continue

                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        record = json.load(f)

                    # Filter by model if specified
                    if model_name and record.get("model_name") != model_name:
                        continue

                    # Create summary
                    summary = {
                        "session_id": record.get("session_id", session_file.stem),
                        "model_name": record.get("model_name", "unknown"),
                        "message_count": record.get("message_count", 0),
                        "saved_at": record.get("saved_at", ""),
                        "preview": self._get_conversation_preview(record.get("chat_history", [])),
                        "metadata": record.get("metadata", {})
                    }
                    conversations.append(summary)

                except Exception as e:
                    print(f"ChatHistoryManager ERROR: Failed to read {session_file}: {e}")
                    continue

            # Sort by saved_at (most recent first)
            conversations.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
            return conversations

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to list conversations: {e}")
            return []

    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            session_file = self.history_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                self._remove_from_index(session_id)
                return True
            return False

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to delete conversation: {e}")
            return False

    def rename_conversation(self, session_id: str, new_name: str) -> bool:
        """
        Rename a conversation

        Args:
            session_id: Current session ID
            new_name: New session name

        Returns:
            True if renamed successfully
        """
        try:
            # Clean new name
            new_name = "".join(c for c in new_name if c.isalnum() or c in ('_', '-', ' '))
            new_name = new_name.replace(' ', '_')

            old_file = self.history_dir / f"{session_id}.json"
            new_file = self.history_dir / f"{new_name}.json"

            if not old_file.exists():
                return False

            if new_file.exists():
                print(f"ChatHistoryManager ERROR: Session name '{new_name}' already exists")
                return False

            # Load, update, and save
            with open(old_file, 'r', encoding='utf-8') as f:
                record = json.load(f)

            record["session_id"] = new_name

            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2)

            # Delete old file
            old_file.unlink()

            # Update index
            self._remove_from_index(session_id)
            self._update_index(new_name, record["model_name"], record["message_count"])

            return True

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to rename conversation: {e}")
            return False

    def get_latest_conversation(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent conversation for a model

        Args:
            model_name: Model name to search for

        Returns:
            Conversation record or None
        """
        conversations = self.list_conversations(model_name)
        if conversations:
            return self.load_conversation(conversations[0]["session_id"])
        return None

    def _get_conversation_preview(self, chat_history: List[Dict[str, Any]], max_length: int = 100) -> str:
        """Generate a preview of the conversation"""
        if not chat_history:
            return "Empty conversation"

        # Get first user message
        for msg in chat_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if len(content) > max_length:
                    return content[:max_length] + "..."
                return content

        return "No user messages"

    def _update_index(self, session_id: str, model_name: str, message_count: int):
        """Update the index file"""
        try:
            # Load existing index
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
            else:
                index = {}

            # Update entry
            index[session_id] = {
                "model_name": model_name,
                "message_count": message_count,
                "saved_at": datetime.now().isoformat()
            }

            # Save index
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to update index: {e}")

    def _remove_from_index(self, session_id: str):
        """Remove entry from index"""
        try:
            if not self.index_file.exists():
                return

            with open(self.index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)

            if session_id in index:
                del index[session_id]

            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to remove from index: {e}")

    def export_conversation(self, session_id: str, export_path: Path, format: str = "json") -> bool:
        """
        Export conversation to a file

        Args:
            session_id: Session to export
            export_path: Path to save export
            format: Export format (json, txt, md)

        Returns:
            True if exported successfully
        """
        try:
            conversation = self.load_conversation(session_id)
            if not conversation:
                return False

            if format == "json":
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(conversation, f, indent=2)

            elif format == "txt":
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(f"Conversation: {session_id}\n")
                    f.write(f"Model: {conversation['model_name']}\n")
                    f.write(f"Saved: {conversation['saved_at']}\n")
                    f.write("=" * 80 + "\n\n")

                    for msg in conversation['chat_history']:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        f.write(f"[{role.upper()}]\n{content}\n\n")

            elif format == "md":
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {session_id}\n\n")
                    f.write(f"**Model:** {conversation['model_name']}  \n")
                    f.write(f"**Saved:** {conversation['saved_at']}  \n\n")
                    f.write("---\n\n")

                    for msg in conversation['chat_history']:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        f.write(f"### {role.capitalize()}\n\n{content}\n\n")

            return True

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to export conversation: {e}")
            return False

    def extract_training_examples(
        self,
        model_name: Optional[str] = None,
        min_tool_calls: int = 1,
        successful_only: bool = True,
        output_file: Optional[Path] = None
    ) -> str:
        """
        Extract training examples from saved chat conversations.
        Focuses on conversations with successful tool usage.

        Args:
            model_name: Filter by specific model (None for all)
            min_tool_calls: Minimum tool calls required in a conversation
            successful_only: Only include conversations where tools succeeded
            output_file: Path to save training data (default: auto-generate)

        Returns:
            Path to the generated training file
        """
        try:
            # Generate output file path if not provided
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                model_suffix = f"_{model_name}" if model_name else "_all"
                training_dir = self.history_dir.parent / "Training"
                training_dir.mkdir(parents=True, exist_ok=True)
                output_file = training_dir / f"chat_extracted{model_suffix}_{timestamp}.jsonl"

            # Get all conversations
            conversations = self.list_conversations(model_name)

            training_examples = []
            total_extracted = 0

            for conv_summary in conversations:
                # Load full conversation
                conversation = self.load_conversation(conv_summary['session_id'])
                if not conversation:
                    continue

                chat_history = conversation.get('chat_history', [])

                # Count tool calls in this conversation
                tool_call_count = 0
                has_errors = False

                for msg in chat_history:
                    if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                        tool_call_count += len(msg['tool_calls'])

                    # Check for errors in tool results
                    if msg.get('role') == 'tool':
                        content = msg.get('content', '')
                        if 'Error:' in content or 'error' in content.lower():
                            has_errors = True

                # Filter based on criteria
                if tool_call_count < min_tool_calls:
                    continue

                if successful_only and has_errors:
                    continue

                # Extract training examples from this conversation
                # We'll create examples from successful tool usage patterns
                example = self._create_training_example_from_conversation(chat_history)

                if example:
                    training_examples.append(example)
                    total_extracted += 1

            # Write to JSONL file
            with open(output_file, 'w', encoding='utf-8') as f:
                for example in training_examples:
                    f.write(json.dumps(example) + '\n')

            print(f"ChatHistoryManager: Extracted {total_extracted} training examples to {output_file}")
            return str(output_file)

        except Exception as e:
            print(f"ChatHistoryManager ERROR: Failed to extract training examples: {e}")
            return ""

    def _create_training_example_from_conversation(
        self,
        chat_history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a training example from a conversation with tool usage.

        Extracts the pattern: system → user → assistant (with tool_calls) → tool → assistant (final)
        """
        if not chat_history:
            return None

        # Find segments with tool usage
        # Look for: user message → assistant with tool_calls → tool results → assistant final response
        messages_for_training = []

        i = 0
        while i < len(chat_history):
            msg = chat_history[i]

            # Start collecting when we see a user message
            if msg.get('role') == 'user':
                segment = []

                # Add system message if there's one before
                if i > 0 and chat_history[i-1].get('role') == 'system':
                    segment.append(chat_history[i-1])

                # Add user message
                segment.append(msg)

                # Look ahead for assistant with tool calls
                if i + 1 < len(chat_history):
                    next_msg = chat_history[i + 1]
                    if next_msg.get('role') == 'assistant' and 'tool_calls' in next_msg:
                        # Found tool usage! Add the sequence
                        segment.append(next_msg)

                        # Add tool results
                        j = i + 2
                        while j < len(chat_history) and chat_history[j].get('role') == 'tool':
                            segment.append(chat_history[j])
                            j += 1

                        # Add final assistant response if present
                        if j < len(chat_history) and chat_history[j].get('role') == 'assistant':
                            segment.append(chat_history[j])

                        # This is a complete tool usage example
                        if len(segment) >= 4:  # user + assistant + tool + assistant
                            messages_for_training.extend(segment)
                            i = j
                            continue

            i += 1

        # If we found tool usage patterns, create training example
        if messages_for_training:
            return {"messages": messages_for_training}

        return None


# Convenience singleton instance
_global_manager = None


def get_history_manager(history_dir: Optional[Path] = None) -> ChatHistoryManager:
    """Get the global history manager instance (singleton pattern)"""
    global _global_manager
    if _global_manager is None:
        _global_manager = ChatHistoryManager(history_dir)
    return _global_manager
