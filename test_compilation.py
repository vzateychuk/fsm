"""Простой тест компилируемости"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test 1: Import core types
print("Test 1: Importing core types...", end=" ")
from fsm.core import RunContext, SagaDefinition, SagaStep, SagaProgressStore
print("OK")

# Test 2: Import saga components
print("Test 2: Importing saga components...", end=" ")
from saga.saga import Saga
from saga.models import SagaInput, SagaState, Preprocessing, Processing
print("OK")

# Test 3: Import store components
print("Test 3: Importing store components...", end=" ")
from store.store import Store, SavedProgress
from store.sql.sql_store import SQLStore
print("OK")

# Test 4: Instantiate saga definition
print("Test 4: Creating saga definition...", end=" ")
definition = SagaDefinition[SagaInput, SagaState](
    name="test_saga",
    steps=[Preprocessing(), Processing()],
)
print("OK")

# Test 5: Create saga with store
print("Test 5: Creating saga with SQLStore...", end=" ")
store = SQLStore()
saga = Saga(definition, store, SagaState)
print("OK")

print("\nAll tests passed! Project is compilable.")
