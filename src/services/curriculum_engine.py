"""Curriculum Engine — loads and indexes curriculum.json at startup.

Provides O(1) lookups for days, modules, and day-to-module mappings.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.curriculum import Curriculum, CurriculumIndex, DayEntry, ModuleEntry


class CurriculumEngine:
    """Loads curriculum.json and provides indexed access to curriculum data."""

    def __init__(self) -> None:
        self._curriculum: Curriculum | None = None
        self._index: CurriculumIndex | None = None

    def load(self, curriculum_path: str | Path) -> None:
        """Load and index curriculum.json from disk.

        Args:
            curriculum_path: Path to curriculum.json file.

        Raises:
            FileNotFoundError: If curriculum file is missing.
            ValueError: If curriculum format is invalid.
        """
        path = Path(curriculum_path)
        if not path.exists():
            raise FileNotFoundError(f"Curriculum file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self._curriculum = Curriculum.model_validate(raw)
        self._build_index()

    def _build_index(self) -> None:
        """Build O(1) lookup indexes from the parsed curriculum."""
        if self._curriculum is None:
            raise ValueError("Curriculum not loaded")

        day_by_number: dict[int, DayEntry] = {}
        module_by_number: dict[int, ModuleEntry] = {}
        day_to_module: dict[int, int] = {}

        for module in self._curriculum.modules:
            module_by_number[module.n] = module
            for day_num in range(module.start_day, module.end_day + 1):
                day_to_module[day_num] = module.n

        for day in self._curriculum.days:
            day_by_number[day.day] = day

        self._index = CurriculumIndex(
            day_by_number=day_by_number,
            module_by_number=module_by_number,
            day_to_module=day_to_module,
            modules_list=list(self._curriculum.modules),
            days_list=list(self._curriculum.days),
        )

    @property
    def index(self) -> CurriculumIndex:
        """Get the curriculum index."""
        if self._index is None:
            raise ValueError("Curriculum not loaded. Call load() first.")
        return self._index

    def get_day(self, day_number: int) -> DayEntry | None:
        """Get a curriculum day by its number."""
        return self.index.day_by_number.get(day_number)

    def get_module(self, module_number: int) -> ModuleEntry | None:
        """Get a curriculum module by its number."""
        return self.index.module_by_number.get(module_number)

    def get_module_for_day(self, day_number: int) -> int | None:
        """Get module number containing the given day."""
        return self.index.day_to_module.get(day_number)

    def get_days_in_module(self, module_number: int) -> list[DayEntry]:
        """Get all days belonging to a module."""
        module = self.get_module(module_number)
        if module is None:
            return []
        return [
            day for day in self.index.days_list
            if module.contains_day(day.day)
        ]

    def get_uncovered_days_in_module(self, module_number: int, covered_days: set[int]) -> list[DayEntry]:
        """Get days in a module not yet covered."""
        return [
            day for day in self.get_days_in_module(module_number)
            if day.day not in covered_days
        ]

    @property
    def all_days(self) -> list[DayEntry]:
        return self.index.days_list

    @property
    def all_modules(self) -> list[ModuleEntry]:
        return self.index.modules_list

    @property
    def total_days(self) -> int:
        return len(self.index.days_list)

    @property
    def total_modules(self) -> int:
        return len(self.index.modules_list)
