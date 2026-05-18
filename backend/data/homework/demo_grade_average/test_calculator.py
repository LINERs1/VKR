"""Автотесты для ДЗ «Калькулятор среднего балла»."""

import pytest

from calculator import Student, average


def test_average_simple():
    assert average([5, 4, 3]) == pytest.approx(4.0)


def test_average_empty_raises():
    with pytest.raises(ValueError, match="пустым"):
        average([])


def test_student_average_grade():
    s = Student("Анна", [5, 5, 4])
    assert s.average_grade() == pytest.approx(14 / 3)


def test_student_is_passing():
    assert Student("Иван", [5, 5, 5]).is_passing()
    assert not Student("Пётр", [2, 3, 2]).is_passing(threshold=4.0)


def test_student_name_stored():
    s = Student("Мария", [4])
    assert s.name == "Мария"
