"""Quick test script to verify text-to-speech functionality."""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.voice import speak_items
import time

print("Testing voice output...")
print("-" * 50)

# Test 1: Single object
print("\nTest 1: Single object")
speak_items(["person"])
time.sleep(2)

# Test 2: Two objects
print("\nTest 2: Two objects")
speak_items(["person", "chair"])
time.sleep(3)

# Test 3: Multiple objects
print("\nTest 3: Multiple objects")
speak_items(["person", "chair", "bottle"])
time.sleep(4)

# Test 4: With counts (as it would be called from app.py)
print("\nTest 4: Multiple objects with counts")
speak_items(["2 persons", "chair", "3 bottles"])
time.sleep(4)

# Test 5: Repetition avoidance
print("\nTest 5: Repetition avoidance (should speak)")
speak_items(["person", "chair"], avoid_repetition=True)
time.sleep(3)

print("\nTest 6: Same objects again (should NOT speak)")
speak_items(["person", "chair"], avoid_repetition=True)
time.sleep(1)

print("\nTest 7: Different objects (should speak)")
speak_items(["bottle", "laptop"], avoid_repetition=True)
time.sleep(3)

print("\n" + "-" * 50)
print("Voice tests completed!")
print("If you heard all the sentences, voice is working correctly.")
