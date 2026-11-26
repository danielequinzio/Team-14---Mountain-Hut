from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import Booking, CopyWeekScheduleRequest, Slot, SlotTable

HUT_TIMEZONE = ZoneInfo("Europe/Rome")


def hut_time(value: datetime) -> datetime:
    # sqlite gives the datetime back without its timezone: it is the hut's local time
    if value.tzinfo is None:
        return value.replace(tzinfo=HUT_TIMEZONE)
    return value.astimezone(HUT_TIMEZONE)


def slot_start(slot: Slot) -> datetime:
    return hut_time(slot.start_time)


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _create_week_copies(
    source_slots: list[Slot],
    unaffected_slots: list[Slot],
    source_week_start: date,
    target_week_start: date,
    number_of_weeks: int,
    created_by: int,
) -> tuple[list[Slot], list[tuple[Slot, Slot]]]:
    copies = []
    copy_sources = []
    base_offset = target_week_start - source_week_start

    for week_index in range(number_of_weeks):
        offset = base_offset + timedelta(weeks=week_index)
        for source in source_slots:
            start = hut_time(source.start_time) + offset
            end = hut_time(source.end_time) + offset
            if any(
                hut_time(existing.start_time) < end
                and start < hut_time(existing.end_time)
                for existing in unaffected_slots + copies
            ):
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "The copied schedule overlaps an existing slot",
                )

            copy = Slot(start_time=start, end_time=end, created_by=created_by)
            copies.append(copy)
            copy_sources.append((source, copy))

    return copies, copy_sources


def copy_week_schedule(
    session: Session,
    data: CopyWeekScheduleRequest,
    created_by: int,
) -> list[Slot]:
    source_week_start = _week_start(data.source_week)
    target_week_start = _week_start(data.target_week)
    current_week_start = _week_start(datetime.now(HUT_TIMEZONE).date())
    if target_week_start <= current_week_start:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The target week must be in the future",
        )
    if target_week_start <= source_week_start:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The target week must be after the source week",
        )

    all_slots = session.exec(select(Slot).order_by(Slot.start_time)).all()
    source_week_end = source_week_start + timedelta(days=7)
    source_slots = sorted(
        (
            slot for slot in all_slots
            if source_week_start <= slot_start(slot).date() < source_week_end
        ),
        key=slot_start,
    )
    if not source_slots:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The source week has no slots")

    target_week_end = target_week_start + timedelta(weeks=data.number_of_weeks)
    target_slots = [
        slot for slot in all_slots
        if target_week_start <= slot_start(slot).date() < target_week_end
    ]
    target_slot_ids = [slot.id for slot in target_slots]
    if target_slot_ids and session.exec(
        select(Booking).where(Booking.slot_id.in_(target_slot_ids))
    ).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A target week contains bookings and cannot be replaced",
        )

    target_slot_id_set = set(target_slot_ids)
    unaffected_slots = [
        slot for slot in all_slots if slot.id not in target_slot_id_set
    ]
    copies, copy_sources = _create_week_copies(
        source_slots,
        unaffected_slots,
        source_week_start,
        target_week_start,
        data.number_of_weeks,
        created_by,
    )

    source_slot_ids = [slot.id for slot in source_slots]
    source_tables = session.exec(
        select(SlotTable).where(SlotTable.slot_id.in_(source_slot_ids))
    ).all()
    tables_by_source: dict[int, list[int]] = {}
    for source_table in source_tables:
        tables_by_source.setdefault(source_table.slot_id, []).append(source_table.table_id)

    if target_slot_ids:
        target_tables = session.exec(
            select(SlotTable).where(SlotTable.slot_id.in_(target_slot_ids))
        ).all()
        for table in target_tables:
            session.delete(table)
        session.flush()
        for slot in target_slots:
            session.delete(slot)
        session.flush()

    session.add_all(copies)
    session.flush()
    session.add_all(
        [
            SlotTable(slot_id=copy.id, table_id=table_id)
            for source, copy in copy_sources
            for table_id in tables_by_source.get(source.id, [])
        ]
    )
    return copies
