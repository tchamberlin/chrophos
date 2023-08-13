from numbers import Number

from abc import abstractmethod

from typing import Any


class Parameter:
    """"""

    def __init__(self, name: str, field: str, initial_value: Any):
        self.name = name
        self.field = field
        self.value = initial_value
        self.validate()

    def __str__(self):
        return self.name

    @abstractmethod
    def validate(self):
        pass


class ReadonlyParameter(Parameter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self):
        pass


class ValidationError(ValueError):
    """"""


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
                f"{self.value} is not within valid range [{self.lower_bound}, {self.upper_bound}]"
            )


class DiscreteParameter(Parameter):
    def __init__(self, name: str, field: str, valid_values: list[Any], *args, **kwargs):
        self.valid_values = valid_values
        super().__init__(name=name, field=field, *args, **kwargs)

    def step_value(self, step=1):
        current_index = self.valid_values.index(self.value)
        if step == 0:
            return self.value

        if 0 <= self.valid_values.index(self.value) + step < len(self.valid_values):
            new_value = self.valid_values[current_index + step]
            self.value = new_value
        else:
            raise IndexError(f"Can't step value by {step}!")
        return self.value

    def increment(self, step=1):
        return self.step_value(step)

    def decrement(self, step=-1):
        return self.step_value(step)

    def validate(self):
        if self.value not in self.valid_values:
            raise ValidationError(f"{self.value} is not in valid values {self.valid_values}")
