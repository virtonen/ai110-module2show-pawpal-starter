"""Basic behaviour tests for the PawPal+ core classes."""

import pytest

from pawpal_system import Category, Pet, Priority, Task


@pytest.fixture
def task() -> Task:
    return Task("Morning walk", Category.WALK, 30, Priority.HIGH)


@pytest.fixture
def pet() -> Pet:
    return Pet(name="Rex", species="dog")


def test_mark_complete_changes_task_status(task):
    assert task.completed is False  # precondition: starts incomplete

    task.mark_complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count(pet, task):
    assert len(pet.tasks) == 0  # precondition: no tasks yet

    pet.add_task(task)

    assert len(pet.tasks) == 1
    assert task in pet.tasks
