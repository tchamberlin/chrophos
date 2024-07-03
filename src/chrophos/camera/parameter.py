import logging
from abc import abstractmethod
from numbers import Number
from typing import Any, Callable

logger = logging.getLogger("chrophos")


class ValidationError(ValueError):
    ...


class Parameter:
    def __init__(
        self, name: str, field: str, initial_value: Any = None, setter: Callable | None = None
    ):
        self.name = name
        self.field = field
        self._value = initial_value
        self.validate()
        self.setter = setter

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
        original_value = self._value
        self._value = value
        self.validate()
        if self.setter:
            logger.warning(f"Calling setter function {self.setter.__name__}({self.field}, {value})")
            self.setter(params=[self])
            logger.debug(f"Changed {self.name} ({self.field}) from {original_value} to {value}")

    @abstractmethod
    def parse(self, value: str):
        ...


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
        super().__init__(*args, name=name, field=field, **kwargs)

    # def get_value(self):
    #     pass

    def validate(self):
        if not (self.lower_bound <= self.value <= self.upper_bound):
            raise ValidationError(
                f"{self.field} {self.value} is not within valid range [{self.lower_bound},"
                f" {self.upper_bound}]"
            )


class DiscreteParameter(Parameter):
    def __init__(self, name: str, field: str, choices: list[Any], *args, **kwargs):
        self.choices = choices
        super().__init__(*args, name=name, field=field, **kwargs)

    def step_value(self, step: int):
        current_index = self.choices.index(self.value)
        if step == 0:
            return self.value

        if 0 <= self.choices.index(self.value) + step < len(self.choices):
            new_value = self.choices[current_index + step]
            self.value = new_value
            self.validate()
        else:
            raise ValidationError(f"Can't step value by {step}!")
        return self.value

    def increment(self, step=1):
        return self.step_value(step)

    def decrement(self, step=-1):
        return self.step_value(step)

    def validate(self):
        if self.value not in self.choices:
            raise ValidationError(
                f"{self.field} value {self.value!r} is not in valid values {self.choices}"
            )

    def parse(self, value):
        ...

    @property
    def actual_value(self):
        return self.parse(self.value)
