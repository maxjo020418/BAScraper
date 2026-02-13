from datetime import datetime, timezone
import logging
from typing import Any, Tuple
from zoneinfo import ZoneInfo
import warnings

from pydantic_extra_types.pendulum_dt import DateTime


def tz_is_utc(timezone_name: str) -> bool:
    normalized = timezone_name.strip().lower()
    return normalized in {"utc", "etc/utc", "gmt", "etc/gmt"}


def parse_datetime_string(raw: str) -> datetime:
    raw_stripped = raw.strip()
    raw_iso = raw_stripped[:-1] + "+00:00" if raw_stripped.endswith(("Z", "z")) else raw_stripped
    return datetime.fromisoformat(raw_iso)


def format_epoch_utc(epoch_utc: int) -> str:
    return datetime.fromtimestamp(epoch_utc, tz=timezone.utc).strftime("%y%m%d-%H%M%S")


def localize_temporal_fields(
    data: Any,
    temporal_fields: Tuple[str, ...],
    logger: logging.Logger,
    *,
    timezone_key: str = "timezone",
    default_timezone: str = "UTC",
) -> Any:
    if not isinstance(data, dict):
        return data

    timezone = data.get(timezone_key, default_timezone)
    if tz_is_utc(timezone):
        return data

    tzinfo = ZoneInfo(timezone)
    out = dict(data)
    for field_name in temporal_fields:
        if field_name not in out:
            continue
        value = out[field_name]
        if isinstance(value, datetime):
            if value.tzinfo is None:
                localized = value.replace(tzinfo=tzinfo)
                logger.info(
                    "Timezone localization (%s): %r (assumed %s) -> %r",
                    field_name,
                    value,
                    timezone,
                    localized,
                )
                out[field_name] = localized
        elif isinstance(value, str):
            parsed = parse_datetime_string(value)
            if parsed.tzinfo is None:
                localized = parsed.replace(tzinfo=tzinfo)
                logger.info(
                    "Timezone localization (%s): %r (assumed %s) -> %r",
                    field_name,
                    value,
                    timezone,
                    localized,
                )
                parsed = localized
            out[field_name] = parsed

    return out


def validate_temporal_value(
    value: DateTime | datetime | int | str | None,
) -> DateTime | datetime | int | None:
    if isinstance(value, str):
        raise ValueError("Value must be a valid datetime (ISO 8601) or integer timestamp (epoch)")
    return value


def normalize_datetime_fields(
    model: Any,
    temporal_fields: Tuple[str, ...],
    timezone: str,
    logger: logging.Logger,
) -> None:
    for attr in temporal_fields:
        value = getattr(model, attr)
        if isinstance(value, DateTime):  # pass for int and None
            epoch_utc = value.int_timestamp
            if not tz_is_utc(timezone):
                logger.info(
                    "Normalization to epoch UTC (%s): %r -> %s (%d)",
                    attr,
                    value,
                    format_epoch_utc(epoch_utc),
                    epoch_utc,
                )
            setattr(model, attr, epoch_utc)
        elif isinstance(value, datetime):
            if value.tzinfo is None:
                tzinfo = ZoneInfo(timezone)
                localized = value.replace(tzinfo=tzinfo)
                logger.info(
                    "Timezone localization (%s): %r (assumed %s) -> %r",
                    attr,
                    value,
                    timezone,
                    localized,
                )
                value = localized
            epoch_utc = int(value.timestamp())
            if not tz_is_utc(timezone):
                logger.info(
                    "Normalization to epoch UTC (%s): %r -> %s (%d)",
                    attr,
                    value,
                    format_epoch_utc(epoch_utc),
                    epoch_utc,
                )
            setattr(model, attr, epoch_utc)


def validate_temporal_order(
    after: DateTime | datetime | int | str | None,
    before: DateTime | datetime | int | str | None,
) -> None:
    if isinstance(after, str) or isinstance(before, str):
        raise ValueError("Value must be a valid datetime (ISO 8601) or integer timestamp (epoch)")

    if isinstance(after, DateTime):
        after = after.int_timestamp
    if isinstance(before, DateTime):
        before = before.int_timestamp
    if isinstance(after, datetime):
        if after.tzinfo is None:
            raise ValueError("Timezone-naive datetime provided for 'after'.")
        after = int(after.timestamp())
    if isinstance(before, datetime):
        if before.tzinfo is None:
            raise ValueError("Timezone-naive datetime provided for 'before'.")
        before = int(before.timestamp())

    if isinstance(after, int) and isinstance(before, int):
        if after >= before:
            raise ValueError("'after' must be less than 'before'.")
    elif after is not None and before is None:
        warnings.warn(
            "'after' is set but 'before' is not, "
            "BAScraper will not attempt to iterate and will only fetch a single page of results.",
            UserWarning,
        )
    elif after is None and isinstance(before, int):
        warnings.warn(
            "'before' is set but 'after' is not, "
            "BAScraper will not attempt to iterate and will only fetch a single page of results.",
            UserWarning,
        )
    else:  # both None
        warnings.warn(
            "'after' and 'before' are both None, "
            "BAScraper will not attempt to iterate and will only fetch a single page of results. "
            "(limited to 100 entries)",
            UserWarning,
        )
