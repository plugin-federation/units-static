#!/usr/bin/env python3
"""
units-static: High-quality MCP server for deterministic unit conversion.

Exposes a small, well-described tool surface for length, mass, temperature,
and volume conversions against fixed SI conversion tables (no network I/O).
Intended as a "good MCP" dogfood companion for Plugin Federation judges and
evals — tools are designed for high schema-clarity scores.

Usage:
    # STDIO (default)
    python src/server.py

    # Streamable HTTP
    python src/server.py --transport http --port 8000
"""

from __future__ import annotations

import argparse
from enum import Enum
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP(
    "units-static",
    instructions=(
        "Deterministic unit conversion helpers. Prefer list_units when you need "
        "valid unit identifiers, then call the matching convert_* tool for the "
        "quantity dimension. All conversions are exact table lookups (static data)."
    ),
)

# -- Enums (expose as closed sets in inputSchema) ---------------------------


class LengthUnit(str, Enum):
    meter = "meter"
    kilometer = "kilometer"
    centimeter = "centimeter"
    millimeter = "millimeter"
    mile = "mile"
    yard = "yard"
    foot = "foot"
    inch = "inch"
    nautical_mile = "nautical_mile"


class MassUnit(str, Enum):
    kilogram = "kilogram"
    gram = "gram"
    milligram = "milligram"
    pound = "pound"
    ounce = "ounce"
    ton_metric = "ton_metric"
    stone = "stone"


class TemperatureUnit(str, Enum):
    celsius = "celsius"
    fahrenheit = "fahrenheit"
    kelvin = "kelvin"


class VolumeUnit(str, Enum):
    liter = "liter"
    milliliter = "milliliter"
    cubic_meter = "cubic_meter"
    us_gallon = "us_gallon"
    us_quart = "us_quart"
    us_cup = "us_cup"
    us_fluid_ounce = "us_fluid_ounce"
    imperial_gallon = "imperial_gallon"


class Dimension(str, Enum):
    length = "length"
    mass = "mass"
    temperature = "temperature"
    volume = "volume"


# -- Conversion tables (to SI base) ----------------------------------------

# Length → meters
_LENGTH_TO_M: dict[str, float] = {
    "meter": 1.0,
    "kilometer": 1000.0,
    "centimeter": 0.01,
    "millimeter": 0.001,
    "mile": 1609.344,
    "yard": 0.9144,
    "foot": 0.3048,
    "inch": 0.0254,
    "nautical_mile": 1852.0,
}

# Mass → kilograms
_MASS_TO_KG: dict[str, float] = {
    "kilogram": 1.0,
    "gram": 0.001,
    "milligram": 1e-6,
    "pound": 0.45359237,
    "ounce": 0.028349523125,
    "ton_metric": 1000.0,
    "stone": 6.35029318,
}

# Volume → liters
_VOLUME_TO_L: dict[str, float] = {
    "liter": 1.0,
    "milliliter": 0.001,
    "cubic_meter": 1000.0,
    "us_gallon": 3.785411784,
    "us_quart": 0.946352946,
    "us_cup": 0.2365882365,
    "us_fluid_ounce": 0.0295735295625,
    "imperial_gallon": 4.54609,
}

_UNIT_CATALOG: dict[str, list[str]] = {
    "length": list(_LENGTH_TO_M.keys()),
    "mass": list(_MASS_TO_KG.keys()),
    "temperature": [u.value for u in TemperatureUnit],
    "volume": list(_VOLUME_TO_L.keys()),
}


# -- Output models ---------------------------------------------------------


class UnitInfo(BaseModel):
    id: str = Field(description="Stable unit identifier accepted by convert tools.")
    dimension: Dimension = Field(description="Physical dimension this unit belongs to.")
    symbol: str = Field(description="Common short symbol for display (e.g. 'km', 'lb').")
    description: str = Field(description="Human-readable unit label.")


class ListUnitsResult(BaseModel):
    dimensions: list[Dimension] = Field(
        description="Dimensions available for conversion on this server."
    )
    units: list[UnitInfo] = Field(
        description="Complete catalog of unit identifiers, grouped by dimension."
    )
    count: int = Field(description="Total number of unit identifiers in the catalog.")


class ConvertResult(BaseModel):
    value: float = Field(description="Converted numeric value in the target unit.")
    from_unit: str = Field(description="Source unit identifier that was converted from.")
    to_unit: str = Field(description="Target unit identifier that was converted to.")
    dimension: Dimension = Field(description="Physical dimension of the conversion.")
    formula_note: str = Field(
        description="Short note describing how the conversion was computed."
    )


class CompareResult(BaseModel):
    left_value: float = Field(description="Left-hand quantity after normalization.")
    right_value: float = Field(description="Right-hand quantity after normalization.")
    unit: str = Field(description="Unit used for the comparison result values.")
    dimension: Dimension = Field(description="Physical dimension of both quantities.")
    difference: float = Field(
        description="left_value - right_value in the comparison unit."
    )
    relation: Literal["greater", "less", "equal"] = Field(
        description="Whether the left quantity is greater, less, or equal to the right."
    )


_UNIT_META: dict[str, tuple[str, str]] = {
    # length: (symbol, description)
    "meter": ("m", "SI base length"),
    "kilometer": ("km", "1000 meters"),
    "centimeter": ("cm", "0.01 meters"),
    "millimeter": ("mm", "0.001 meters"),
    "mile": ("mi", "International mile"),
    "yard": ("yd", "Imperial yard"),
    "foot": ("ft", "Imperial foot"),
    "inch": ("in", "Imperial inch"),
    "nautical_mile": ("nmi", "International nautical mile"),
    # mass
    "kilogram": ("kg", "SI base mass"),
    "gram": ("g", "0.001 kilograms"),
    "milligram": ("mg", "0.000001 kilograms"),
    "pound": ("lb", "International avoirdupois pound"),
    "ounce": ("oz", "International avoirdupois ounce"),
    "ton_metric": ("t", "Metric ton (1000 kg)"),
    "stone": ("st", "Imperial stone (14 lb)"),
    # temperature
    "celsius": ("°C", "Celsius temperature scale"),
    "fahrenheit": ("°F", "Fahrenheit temperature scale"),
    "kelvin": ("K", "Absolute thermodynamic temperature"),
    # volume
    "liter": ("L", "SI-accepted volume"),
    "milliliter": ("mL", "0.001 liters"),
    "cubic_meter": ("m³", "SI cubic meter"),
    "us_gallon": ("gal", "US liquid gallon"),
    "us_quart": ("qt", "US liquid quart"),
    "us_cup": ("cup", "US customary cup"),
    "us_fluid_ounce": ("fl oz", "US fluid ounce"),
    "imperial_gallon": ("imp gal", "Imperial gallon"),
}


def _round_value(value: float) -> float:
    """Stable rounding for JSON-friendly deterministic results."""
    return float(f"{value:.12g}")


def _convert_linear(
    value: float,
    from_unit: str,
    to_unit: str,
    table: dict[str, float],
    dimension: Dimension,
) -> ConvertResult:
    if from_unit not in table:
        raise ValueError(f"Unsupported {dimension.value} unit: {from_unit}")
    if to_unit not in table:
        raise ValueError(f"Unsupported {dimension.value} unit: {to_unit}")
    base = value * table[from_unit]
    result = base / table[to_unit]
    return ConvertResult(
        value=_round_value(result),
        from_unit=from_unit,
        to_unit=to_unit,
        dimension=dimension,
        formula_note=(
            f"Converted via SI base factor table for {dimension.value} "
            f"({from_unit} → base → {to_unit})."
        ),
    )


def _temp_to_kelvin(value: float, unit: str) -> float:
    if unit == "kelvin":
        return value
    if unit == "celsius":
        return value + 273.15
    if unit == "fahrenheit":
        return (value - 32.0) * (5.0 / 9.0) + 273.15
    raise ValueError(f"Unsupported temperature unit: {unit}")


def _kelvin_to_temp(kelvin: float, unit: str) -> float:
    if unit == "kelvin":
        return kelvin
    if unit == "celsius":
        return kelvin - 273.15
    if unit == "fahrenheit":
        return (kelvin - 273.15) * (9.0 / 5.0) + 32.0
    raise ValueError(f"Unsupported temperature unit: {unit}")


# -- Tools -----------------------------------------------------------------


@mcp.tool()
def list_units(
    dimension: Dimension | None = Field(
        default=None,
        description=(
            "Optional dimension filter. When omitted, returns every unit this "
            "server supports across length, mass, temperature, and volume. "
            "When set, returns only units for that dimension."
        ),
    ),
) -> ListUnitsResult:
    """List conversion unit identifiers this server accepts.

    Call this before convert_* tools when you need the exact unit id strings
    (for example `kilometer` vs `mile`). Results are static and complete for
    this server — there is no network lookup. Filter by dimension when the
    user already knows they need length, mass, temperature, or volume only.
    """
    dims = [dimension] if dimension is not None else list(Dimension)
    units: list[UnitInfo] = []
    for dim in dims:
        for unit_id in _UNIT_CATALOG[dim.value]:
            symbol, description = _UNIT_META[unit_id]
            units.append(
                UnitInfo(
                    id=unit_id,
                    dimension=dim,
                    symbol=symbol,
                    description=description,
                )
            )
    return ListUnitsResult(
        dimensions=dims,
        units=units,
        count=len(units),
    )


@mcp.tool()
def convert_length(
    value: float = Field(
        description=(
            "Numeric length magnitude to convert. May be negative when modeling "
            "directed distances; zero is allowed."
        ),
    ),
    from_unit: LengthUnit = Field(
        description=(
            "Source length unit id. Must be one of the length ids from list_units "
            "(e.g. meter, kilometer, mile, foot)."
        ),
    ),
    to_unit: LengthUnit = Field(
        description=(
            "Target length unit id. Must be a length unit from list_units. "
            "Use the same dimension as from_unit."
        ),
    ),
) -> ConvertResult:
    """Convert a length quantity between supported length units.

    Use when the user asks to convert distances or sizes (meters, miles, feet,
    inches, nautical miles, etc.). Both units must be length units; for mass,
    temperature, or volume use the dedicated convert_* tool instead. Conversion
    factors are fixed international standards stored in this server.
    """
    return _convert_linear(
        value=value,
        from_unit=from_unit.value,
        to_unit=to_unit.value,
        table=_LENGTH_TO_M,
        dimension=Dimension.length,
    )


@mcp.tool()
def convert_mass(
    value: float = Field(
        description=(
            "Numeric mass magnitude to convert. Must be a finite number; "
            "negative values are rejected because mass is non-negative."
        ),
        ge=0,
    ),
    from_unit: MassUnit = Field(
        description=(
            "Source mass unit id from list_units (e.g. kilogram, pound, ounce)."
        ),
    ),
    to_unit: MassUnit = Field(
        description="Target mass unit id from list_units in the mass dimension.",
    ),
) -> ConvertResult:
    """Convert a mass quantity between supported mass units.

    Use for weight/mass conversion requests such as kilograms to pounds or
    grams to ounces. Do not use this for temperature or length. Values must be
    zero or positive. Factors follow international avoirdupois and SI definitions.
    """
    return _convert_linear(
        value=value,
        from_unit=from_unit.value,
        to_unit=to_unit.value,
        table=_MASS_TO_KG,
        dimension=Dimension.mass,
    )


@mcp.tool()
def convert_temperature(
    value: float = Field(
        description=(
            "Temperature magnitude in from_unit. Absolute zero and below in Kelvin "
            "are rejected; Celsius/Fahrenheit values that map below 0 K are rejected."
        ),
    ),
    from_unit: TemperatureUnit = Field(
        description="Source temperature scale: celsius, fahrenheit, or kelvin.",
    ),
    to_unit: TemperatureUnit = Field(
        description="Target temperature scale: celsius, fahrenheit, or kelvin.",
    ),
) -> ConvertResult:
    """Convert a temperature between Celsius, Fahrenheit, and Kelvin.

    Use when the user asks for temperature scale conversion (for example 32°F
    to Celsius, or body temperature to Kelvin). This is not a weather lookup —
    it only transforms the provided number. Invalid absolute temperatures below
    0 K are rejected with a clear error.
    """
    kelvin = _temp_to_kelvin(value, from_unit.value)
    if kelvin < 0:
        raise ValueError(
            f"Temperature {value} {from_unit.value} is below absolute zero "
            f"({kelvin} K)."
        )
    converted = _kelvin_to_temp(kelvin, to_unit.value)
    return ConvertResult(
        value=_round_value(converted),
        from_unit=from_unit.value,
        to_unit=to_unit.value,
        dimension=Dimension.temperature,
        formula_note=(
            f"Converted via Kelvin bridge "
            f"({from_unit.value} → kelvin → {to_unit.value})."
        ),
    )


@mcp.tool()
def convert_volume(
    value: float = Field(
        description=(
            "Numeric volume magnitude to convert. Must be zero or positive; "
            "negative volumes are rejected."
        ),
        ge=0,
    ),
    from_unit: VolumeUnit = Field(
        description=(
            "Source volume unit id from list_units (e.g. liter, us_gallon, milliliter)."
        ),
    ),
    to_unit: VolumeUnit = Field(
        description="Target volume unit id from list_units in the volume dimension.",
    ),
) -> ConvertResult:
    """Convert a volume quantity between supported volume units.

    Use for liquid measure conversions such as liters to US gallons or cups to
    milliliters. Imperial and US customary units are distinct — pick the exact
    unit id from list_units. Mass and length conversions belong on convert_mass
    and convert_length respectively.
    """
    return _convert_linear(
        value=value,
        from_unit=from_unit.value,
        to_unit=to_unit.value,
        table=_VOLUME_TO_L,
        dimension=Dimension.volume,
    )


@mcp.tool()
def compare_quantities(
    left_value: float = Field(
        description="Numeric magnitude of the left-hand quantity.",
    ),
    left_unit: str = Field(
        description=(
            "Unit id for the left-hand quantity. Must be a unit from list_units "
            "and share the same dimension as right_unit."
        ),
        min_length=1,
        max_length=40,
    ),
    right_value: float = Field(
        description="Numeric magnitude of the right-hand quantity.",
    ),
    right_unit: str = Field(
        description=(
            "Unit id for the right-hand quantity. Must match left_unit's dimension."
        ),
        min_length=1,
        max_length=40,
    ),
    result_unit: str | None = Field(
        default=None,
        description=(
            "Optional unit id for the comparison output. Defaults to left_unit. "
            "Must belong to the same dimension as both inputs."
        ),
        min_length=1,
        max_length=40,
    ),
) -> CompareResult:
    """Compare two quantities that may use different units of the same dimension.

    Use when the user asks which of two measurements is larger (for example
    1 mile vs 2 kilometers) or wants the numeric difference in a chosen unit.
    Both sides must share length, mass, temperature, or volume; mixed dimensions
    are rejected. Temperature comparisons use Kelvin as the absolute bridge.
    """
    left_dim = _dimension_for_unit(left_unit)
    right_dim = _dimension_for_unit(right_unit)
    if left_dim != right_dim:
        raise ValueError(
            f"Cannot compare {left_unit} ({left_dim.value}) with "
            f"{right_unit} ({right_dim.value}); dimensions must match."
        )
    out_unit = result_unit or left_unit
    out_dim = _dimension_for_unit(out_unit)
    if out_dim != left_dim:
        raise ValueError(
            f"result_unit {out_unit} is {out_dim.value}, expected {left_dim.value}."
        )

    left_norm = _convert_any(left_value, left_unit, out_unit, left_dim)
    right_norm = _convert_any(right_value, right_unit, out_unit, left_dim)
    diff = _round_value(left_norm - right_norm)
    if abs(diff) < 1e-12:
        relation: Literal["greater", "less", "equal"] = "equal"
        diff = 0.0
    elif diff > 0:
        relation = "greater"
    else:
        relation = "less"

    return CompareResult(
        left_value=_round_value(left_norm),
        right_value=_round_value(right_norm),
        unit=out_unit,
        dimension=left_dim,
        difference=diff,
        relation=relation,
    )


def _dimension_for_unit(unit: str) -> Dimension:
    for dim, units in _UNIT_CATALOG.items():
        if unit in units:
            return Dimension(dim)
    raise ValueError(
        f"Unknown unit id: {unit}. Call list_units to see supported identifiers."
    )


def _convert_any(
    value: float,
    from_unit: str,
    to_unit: str,
    dimension: Dimension,
) -> float:
    if dimension == Dimension.temperature:
        kelvin = _temp_to_kelvin(value, from_unit)
        if kelvin < 0:
            raise ValueError(
                f"Temperature {value} {from_unit} is below absolute zero."
            )
        return _kelvin_to_temp(kelvin, to_unit)
    if dimension == Dimension.length:
        return value * _LENGTH_TO_M[from_unit] / _LENGTH_TO_M[to_unit]
    if dimension == Dimension.mass:
        if value < 0:
            raise ValueError("Mass values must be >= 0.")
        return value * _MASS_TO_KG[from_unit] / _MASS_TO_KG[to_unit]
    if dimension == Dimension.volume:
        if value < 0:
            raise ValueError("Volume values must be >= 0.")
        return value * _VOLUME_TO_L[from_unit] / _VOLUME_TO_L[to_unit]
    raise ValueError(f"Unsupported dimension: {dimension}")


def main() -> None:
    parser = argparse.ArgumentParser(description="units-static MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port when --transport http (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="streamable-http", host="127.0.0.1", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
