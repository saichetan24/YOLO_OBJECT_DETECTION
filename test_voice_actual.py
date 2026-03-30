"""Test voice output with actual speech to verify what you hear."""
import sys
import os
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.voice import speak_items

print("Voice Test - Listen carefully!")
print("=" * 60)

print("\nTest 1: Speaking 'person and chair'")
print("Expected: 'Detected objects are person and chair'")
speak_items(["person", "chair"])
time.sleep(4)

print("\nTest 2: Speaking 'person, chair and bottle'")
print("Expected: 'Detected objects are person, chair and bottle'")
speak_items(["person", "chair", "bottle"])
time.sleep(5)

print("\nTest 3: Speaking with counts '2 persons and chair'")
print("Expected: 'Detected objects are 2 persons and chair'")
speak_items(["2 persons", "chair"])
time.sleep(4)

print("\n" + "=" * 60)
print("Did you hear the complete sentences?")
print("If not, the voice might be cutting off too quickly.")
