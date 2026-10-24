"""OfficeController for the AI Office Assistant.

Orchestrates the flow: Input -> Intent Detection -> Memory Update -> Generator Execution -> Output
"""
from __future__ import annotations

from typing import Any, Optional

from .memory import ConversationMemory, get_memory, reset_memory
from .intents import detect_intent, format_intent


class OfficeController:
    """Controller that orchestrates the AI Office Assistant flow.

    The processing pipeline:
    1. Input receives user prompt
    2. Intent Detection classifies the user's intent
    3. Memory Update stores the interaction in conversation history
    4. Generator Execution runs the appropriate generator based on intent
    5. Output produces the final result
    """

    def __init__(self):
        """Initialize the controller with memory and intent detector."""
        self.memory = get_memory()
        self._generators: dict[str, Any] = {}

    def register_generator(self, intent_key: str, generator_func) -> None:
        """Register a generator function for a specific intent.

        Args:
            intent_key: The intent category (e.g., 'docx', 'pdf', 'quiz')
            generator_func: Callable that generates output for this intent
        """
        self._generators[intent_key] = generator_func

    def process_input(self, prompt: str) -> dict[str, Any]:
        """Process a user input prompt through the full pipeline.

        Args:
            prompt: The user's natural language input

        Returns:
            Dictionary with processing results including:
                - intent: detected intent
                - formatted_intent: human-readable intent description
                - response: generated output or None
                - memory_update: whether memory was updated
        """
        # Step 1: Detect intent
        intent_dict = detect_intent(prompt)
        formatted = format_intent(intent_dict)

        # Step 2: Update memory with the exchange
        self.memory.add("user", prompt)
        memory_updated = True

        # Step 3: Execute appropriate generator
        response = None
        intent_key = intent_dict.get("intent", "text")
        generator = self._generators.get(intent_key)

        if generator:
            try:
                response = generator(prompt, intent_dict)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Generator error for intent {intent_key}: {e}")
                response = {
                    "error": f"Generator error: {str(e)}",
                    "intent": intent_key,
                }
        else:
            # No specific generator registered, provide default text response
            response = {
                "response": f"I detected intent: {formatted}. No generator registered for '{intent_key}'.",
                "intent": intent_key,
            }

        # Step 4: Add assistant response to memory
        self.memory.add("assistant", str(response) if response else "")

        return {
            "intent": intent_dict,
            "formatted_intent": formatted,
            "response": response,
            "memory_updated": memory_updated,
        }

    def run_cli_loop(self) -> None:
        """Run the CLI input loop for the AI Office Assistant.

        Accepts natural language prompts and processes them until 'quit' or 'exit'.
        """
        print("=" * 60)
        print("AI Office Assistant")
        print("=" * 60)
        print("Type 'quit' or 'exit' to stop")
        print("-" * 60)

        while True:
            try:
                user_input = input("\n> ").strip()

                if user_input.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                result = self.process_input(user_input)

                # Display the response
                if result["response"]:
                    print("\n--- Response ---")
                    print(result["response"])
                    print("----------------")

                # Show intent detection info
                if result["formatted_intent"]:
                    print(f"Intent: {result['formatted_intent']}")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"CLI error: {e}")
                print(f"\nError: {e}")


# Global controller instance
_controller_instance: Optional[OfficeController] = None


def get_controller() -> OfficeController:
    """Get the global OfficeController instance.

    Returns:
        The single OfficeController instance
    """
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = OfficeController()
    return _controller_instance


def reset_controller() -> None:
    """Reset the global controller instance (useful for testing)."""
    global _controller_instance
    _controller_instance = None
    reset_memory()