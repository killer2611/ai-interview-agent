"""Pydantic models mapping curriculum.json schema exactly."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModuleEntry(BaseModel):
    """A module in the curriculum representing a group of days."""

    n: int = Field(..., ge=1, le=8, description="Module number (1-8)")
    title: str = Field(..., description="Module title")
    days: list[int] = Field(..., min_length=2, max_length=2, description="[start_day, end_day] range inclusive")

    @property
    def start_day(self) -> int:
        return self.days[0]

    @property
    def end_day(self) -> int:
        return self.days[1]

    def contains_day(self, day_number: int) -> bool:
        """Check if a given day number falls within this module's range."""
        return self.start_day <= day_number <= self.end_day


class DayEntry(BaseModel):
    """A single day entry in the curriculum."""

    day: int = Field(..., ge=1, le=31, description="Day number (1-31)")
    title: str = Field(..., description="Day title")
    type: str = Field(..., description="Day classification type (e.g. SETUP, DATA_FOUNDATIONS, AI_CORE, etc.)")
    tools: list[str] = Field(default_factory=list, description="Technologies and libraries covered")
    objectives: list[str] = Field(default_factory=list, description="Specific learning objectives")


class Curriculum(BaseModel):
    """Complete curriculum parsed from curriculum.json."""

    cohort: str = Field(..., description="Cohort name and overview")
    modules: list[ModuleEntry] = Field(..., min_length=1)
    days: list[DayEntry] = Field(..., min_length=1)


class CurriculumIndex(BaseModel):
    """Indexed view of the curriculum for O(1) lookups."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    day_by_number: dict[int, DayEntry]
    module_by_number: dict[int, ModuleEntry]
    day_to_module: dict[int, int]
    modules_list: list[ModuleEntry]
    days_list: list[DayEntry]

