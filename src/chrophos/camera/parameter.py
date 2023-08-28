from abc import abstractmethod
from numbers import Number
from typing import Any


class ValidationError(ValueError):
    ...


class Parameter:
    """"""

    def __init__(self, name: str, field: str, initial_value: Any = None):
        self.name = name
        self.field = field
        self._value = initial_value
        self.validate()

    def __str__(self):
        return f"{self.name}: {self.value}"

    @abstractmethod
    def validate(self):
        pass

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.validate()


class ReadonlyParameter(Parameter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self):
        pass


class RangeParameter(Parameter):
    def __init__(self, name: str, field: str, valid_range: tuple[Number, Number], *args, **kwargs):
        self.valid_range = valid_range
        self.valid_range = valid_range
        self.lower_bound, self.upper_bound = valid_range
        super().__init__(name=name, field=field, *args, **kwargs)

    # def get_value(self):
    #     pass

    def validate(self):
        if not (self.lower_bound <= self.value <= self.upper_bound):
            raise ValidationError(
                f"{self.field} {self.value} is not within valid range [{self.lower_bound},"
                f" {self.upper_bound}]"
            )


class DiscreteParameter(Parameter):
    def __init__(self, name: str, field: str, valid_values: list[Any], *args, **kwargs):
        self.valid_values = valid_values
        super().__init__(name=name, field=field, *args, **kwargs)

    def step_value(self, step: int):
        current_index = self.valid_values.index(self.value)
        if step == 0:
            return self.value

        if 0 <= self.valid_values.index(self.value) + step < len(self.valid_values):
            new_value = self.valid_values[current_index + step]
            self.value = new_value
        else:
            raise ValidationError(f"Can't step value by {step}!")
        return self.value

    def increment(self, step=1):
        return self.step_value(step)

    def decrement(self, step=-1):
        return self.step_value(step)

    def validate(self):
        if self.value not in self.valid_values:
            raise ValidationError(
                f"{self.field} value {self.value!r} is not in valid values {self.valid_values}"
            )
