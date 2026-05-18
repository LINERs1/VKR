"""Эталонное решение — класс Student и расчёт среднего балла."""


def average(grades: list[float]) -> float:
    if not grades:
        raise ValueError("Список оценок не может быть пустым")
    return sum(grades) / len(grades)


class Student:
    def __init__(self, name: str, grades: list[float]):
        self.name = name
        self.grades = list(grades)

    def average_grade(self) -> float:
        return average(self.grades)

    def is_passing(self, threshold: float = 4.0) -> bool:
        return self.average_grade() >= threshold
