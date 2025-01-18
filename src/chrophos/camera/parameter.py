import logging
from abc import ABC, abstractmethod
from numbers import Number
from typing import Any, Callable, Union

logger = logging.getLogger("chrophos")


class ValidationError(ValueError):
    ...


class Parameter(ABC):
    direction = 1

    def __init__(
        self,
        name: str,
        field: str,
        initial_value: Any = None,
        setter: Union[Callable, None] = None,
        read_only=False,
    ):
        self.name = name
        self.field = field
        self._value = initial_value
        self.validate()
        self.setter = setter
        self.read_only = read_only
        if self.setter:
            self.setter(params=[self])

    def __repr__(self):
        return f"{self.name}: {self.value}"

    @abstractmethod
    def validate(self):
        ...

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.read_only:
            raise ValueError(f"{self} is read only!")

        original_value = self._value
        self._value = value
        self.validate()
        if self.setter:
            logger.info(f"Calling setter function {self.setter.__name__}({self.field}, {value})")
            self.setter(params=[self])
            logger.debug(f"Changed {self.name} ({self.field}) from {original_value} to {value}")

    @abstractmethod
    def parse(self, value: str) -> Any:
        ...


class RangeParameter(Parameter):
    """INCLUSIVE"""

    def __init__(self, name: str, field: str, valid_range: tuple[Number, Number], *args, **kwargs):
        self.valid_range = valid_range
        self.lower_bound, self.upper_bound = valid_range
        super().__init__(*args, name=name, field=field, **kwargs)

    def __repr__(self):
        return f"{self.name} [{self.lower_bound}, {self.upper_bound}]"

    def parse(self, value: str):
        return value

    def validate(self):
        if self.value is None:
            return
        if not (self.lower_bound <= self.value <= self.upper_bound):
            raise ValidationError(
                f"{self.field} {self.value} is not within valid range [{self.lower_bound},"
                f" {self.upper_bound}]"
            )


class DiscreteParameter(Parameter):
    def __init__(
        self,
        name: str,
        field: str,
        initial_value: Any,
        choices: list[Any],
        valid_min: Union[int, float, None] = None,
        valid_max: Union[int, float, None] = None,
        *args,
        **kwargs,
    ):
        self.valid_min = self.parse(valid_min) if valid_min is not None else None
        self.valid_max = self.parse(valid_max) if valid_max is not None else None
        self.possible_choices = choices
        valid_choices = []
        for choice in choices:
            try:
                self.parse(choice)
            except ValidationError:
                pass
            else:
                valid_choices.append(choice)

        self.choices = [
            choice
            for choice in valid_choices
            if (self.valid_min is None or self.parse(choice) >= self.valid_min)
            and (self.valid_max is None or self.parse(choice) <= self.valid_max)
        ]
        # TODO: This assumes that choices are sorted, but we don't enforce that
        if self.valid_max is not None and self.parse(initial_value) > self.valid_max:
            logger.info(
                f"Requested {initial_value=} is above valid range; setting to last valid choice"
            )
            initial_value = self.choices[-1]
        if self.valid_min is not None and self.parse(initial_value) < self.valid_min:
            logger.info(
                f"Requested {initial_value=} is below valid range; setting to first valid choice"
            )
            initial_value = self.choices[0]

        super().__init__(*args, name=name, field=field, initial_value=initial_value, **kwargs)

    def __repr__(self):
        if len(self.choices) > 3:
            choices_str = f"[{self.choices[0]}, ..., {self.choices[-1]}]"
        else:
            choices_str = str(self.choices)
        return f"{self.name} {choices_str}"

    def step_value(self, step: int):
        current_index = self.choices.index(self.value)
        if step == 0:
            return self.value

        min_possible = 0
        max_possible = len(self.choices)
        is_an_increase = step > 0
        current_position = self.choices.index(self.value)
        requested_position = current_position + step
        amount_we_can_increase_by = max_possible - current_position - 1
        amount_we_can_decrease_by = current_position
        if min_possible <= requested_position < max_possible:
            new_value = self.choices[current_index + step]
            self.value = new_value
            self.validate()
        else:
            if is_an_increase:
                msg = (
                    f"Can't step {self.name} value by {step}! Current position is "
                    f"[{min_possible} : {current_position} : {max_possible}]. i.e. there are only "
                    f"{amount_we_can_increase_by} positions to increase by"
                )
            else:
                msg = (
                    f"Can't step {self.name} value by {step}! Current position is "
                    f"[{min_possible} : {current_position} : {max_possible}]. i.e. there are only "
                    f"{amount_we_can_decrease_by} positions to decrease by"
                )
            raise ValidationError(msg)
        return self.value

    def increment(self, step=1):
        return self.step_value(step)

    def decrement(self, step=-1):
        return self.step_value(step)

    def validate(self):
        # We do not attempt to validate value None
        if self.value is None:
            return

        if self.value not in self.choices:
            raise ValidationError(
                f"{self.field} value {self.value!r} is not in valid values {self.choices}"
            )

    def parse(self, value: Any):
        return value

    @property
    def actual_value(self):
        return self.parse(self.value)


class Aperture(DiscreteParameter):
    # Aperture's "direction" is inverted from other parameters: to increase exposure, f-stop must be decreased
    # direction = -1

    def parse(self, value: str):
        try:
            return float(value)
        except ValueError:
            pass

        try:
            return float(value.split("/")[1])
        except IndexError as error:
            raise ValidationError(f"Invalid aperture: {value!r}") from error


class Shutter(DiscreteParameter):
    def parse(self, value: str):
        try:
            return float(value)
        except ValueError:
            pass

        try:
            numerator, denominator = value.split("/")
            return float(numerator) / float(denominator)
        except (ValueError, IndexError) as error:
            raise ValidationError(f"Invalid shutter value {value!r}") from error


class Iso(DiscreteParameter):
    def parse(self, value: str):
        try:
            return int(value)
        except ValueError as error:
            raise ValidationError(f"Invalid iso value {value!r}") from error


class EvStep(DiscreteParameter):
    def parse(self, value: str):
        try:
            numerator, denominator = value.split("/")
            return float(numerator) / float(denominator)
        except (ValueError, IndexError) as error:
            raise ValidationError(f"Invalid ev step value {value!r}") from error
