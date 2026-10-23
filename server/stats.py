"""Reusable stats: a Gauge (health, stamina, later a monster's health, a door's durability...)
and a Progression (level + exp). Pure logic: they save and send nothing; their owner reacts to
changes through `on_change` (character.py saves and sends the player's).

    session.health.remove(10)        # damage
    session.progression.add_exp(50)  # may level up"""


class Gauge:
    """A value kept between 0 and a maximum."""

    def __init__(self, maximum: int, value: int | None = None, on_change=None):
        self.maximum = maximum
        self.value = maximum if value is None else max(0, min(value, maximum))
        self.on_change = on_change   # function(gauge), or None

    @property
    def is_empty(self) -> bool:
        return self.value == 0

    def add(self, amount: int) -> int:
        """Raises the value (never above the maximum). Returns how much it really rose."""
        return self._set(self.value + max(0, amount))

    def remove(self, amount: int) -> int:
        """Lowers the value (never below 0). Returns how much it really dropped."""
        return -self._set(self.value - max(0, amount))

    def to_dict(self) -> dict:
        return {"value": self.value, "max": self.maximum}

    def _set(self, value: int) -> int:
        new_value = max(0, min(value, self.maximum))
        change = new_value - self.value
        self.value = new_value
        if change and self.on_change:
            self.on_change(self)
        return change


class Progression:
    """A level and the exp gathered toward the next one. exp_to_next(level) = exp_per_level * level."""

    def __init__(self, level: int = 1, exp: int = 0, max_level: int = 100, exp_per_level: int = 100, on_change=None):
        self.max_level = max_level
        self.exp_per_level = exp_per_level
        self.level = max(1, min(level, max_level))
        self.exp = max(0, exp)
        self.on_change = on_change

    def exp_to_next(self, level: int | None = None) -> int:
        return self.exp_per_level * (self.level if level is None else level)

    def add_exp(self, amount: int) -> int:
        """Gains exp; each time it reaches exp_to_next, one level up (the rest carries over).
        Returns the levels gained."""
        start = self.level
        self.exp += max(0, amount)
        while self.level < self.max_level and self.exp >= self.exp_to_next():
            self.exp -= self.exp_to_next()
            self.level += 1
        if self.level == self.max_level:
            self.exp = 0
        self._changed()
        return self.level - start

    def to_dict(self) -> dict:
        return {"level": self.level, "exp": self.exp, "exp_next": self.exp_to_next()}

    def _changed(self):
        if self.on_change:
            self.on_change(self)
