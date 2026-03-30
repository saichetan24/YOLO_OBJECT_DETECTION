"""Test the sentence formatting to verify output."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.voice import _format_sentence

print("Testing sentence formatting:")
print("-" * 60)

# Test cases
test_cases = [
    (["person"], "Single object"),
    (["person", "chair"], "Two objects"),
    (["person", "chair", "bottle"], "Three objects"),
    (["2 persons", "chair"], "With count - two objects"),
    (["2 persons", "chair", "3 bottles"], "With counts - three objects"),
    (["person", "chair", "bottle", "laptop"], "Four objects"),
]

for items, description in test_cases:
    result = _format_sentence(items)
    print(f"\n{description}:")
    print(f"  Input:  {items}")
    print(f"  Output: '{result}'")

print("\n" + "-" * 60)
print("\nThese are the exact sentences the voice will speak.")
