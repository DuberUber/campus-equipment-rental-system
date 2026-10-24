"""Reservation rules: availability, loan limits, check-out and return.

Views and the admin call these functions instead of changing reservations directly, so every rule lives in
one place. They raise django.core.exceptions.ValidationError with a {field: message} dict on a broken rule.
"""
import re
from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import Condition, Equipment, Reservation

# The availability endpoint answers for at most this long a window.
MAX_AVAILABILITY_WINDOW = timedelta(days=120)
DEFAULT_AVAILABILITY_WINDOW = timedelta(days=28)

_DATE_ONLY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def parse_moment(value, *, end_of_day=False):
    """Parse an ISO date or datetime from a query string into an aware datetime.

    A bare date means local midnight; with ``end_of_day`` it means the end of that day (the next midnight),
    so ``?from=2026-10-01&to=2026-10-03`` covers three whole days. Raises ValueError for anything else.
    """
    value = (value or '').strip()
    if _DATE_ONLY.match(value):
        day = parse_date(value)
        if end_of_day:
            day += timedelta(days=1)
        return timezone.make_aware(datetime.combine(day, time.min))
    moment = parse_datetime(value)
    if moment is None:
        raise ValueError(f'"{value}" is not an ISO 8601 date or datetime.')
    return moment if timezone.is_aware(moment) else timezone.make_aware(moment)


def parse_window(start_value, end_value, *, default_length=None, max_length=None):
    """Parse a ``from``/``to`` pair into (start, end). Raises ValidationError with a field dict."""
    try:
        start = parse_moment(start_value) if start_value else timezone.make_aware(
            datetime.combine(timezone.localdate(), time.min)
        )
    except ValueError as exc:
        raise ValidationError({'from': str(exc)})
    try:
        if end_value:
            end = parse_moment(end_value, end_of_day=True)
        elif default_length:
            end = start + default_length
        else:
            raise ValidationError({'to': 'This parameter is required.'})
    except ValueError as exc:
        raise ValidationError({'to': str(exc)})
    if end <= start:
        raise ValidationError({'to': 'The end of the range must be after its start.'})
    if max_length and end - start > max_length:
        raise ValidationError({'to': f'The range can be at most {max_length.days} days long.'})
    return start, end


def lock_equipment(equipment_id):
    """Lock an item's row for the rest of the transaction, so its reservations are checked one at a time."""
    if not connection.features.has_select_for_update:
        # SQLite ignores SELECT ... FOR UPDATE. A no-op write takes its database-wide write lock instead,
        # which makes a concurrent booking wait until this transaction has committed.
        Equipment.objects.filter(pk=equipment_id).update(is_active=models.F('is_active'))
    return Equipment.objects.select_for_update().select_related('category', 'location').get(pk=equipment_id)


def busy_ranges(equipment, start, end, now=None):
    """The times in [start, end) when ``equipment`` is held, in start order.

    Each range is a dict with start_at, end_at, status and is_overdue. An overdue item stays busy until it
    comes back, so its range runs to ``end``.
    """
    now = now or timezone.now()
    ranges = []
    for reservation in Reservation.objects.filter(equipment=equipment).blocking(start, end, now).order_by('start_at'):
        overdue = reservation.compute_overdue(now)
        ranges.append({
            'start_at': reservation.start_at,
            'end_at': max(reservation.due_at, end) if overdue else reservation.due_at,
            'status': reservation.status,
            'is_overdue': overdue,
        })
    return ranges


def available_equipment(queryset, start, end, now=None):
    """Narrow an Equipment queryset to reservable items that are free for the whole of [start, end)."""
    blocking = Reservation.objects.filter(equipment=models.OuterRef('pk')).blocking(start, end, now)
    return queryset.filter(is_active=True).exclude(condition=Condition.NEEDS_REPAIR).filter(~models.Exists(blocking))


def max_active_reservations():
    return getattr(settings, 'MAX_ACTIVE_RESERVATIONS', 3)


def create_reservation(*, student, equipment, start_at, due_at, notes='', now=None):
    """Reserve ``equipment`` for ``student`` from start_at to due_at, enforcing every booking rule."""
    now = now or timezone.now()
    if student.is_staff:
        raise ValidationError({'student': 'Only students can reserve equipment.'})
    if start_at < now:
        raise ValidationError({'start_at': 'Reservations cannot start in the past.'})
    if due_at <= start_at:
        raise ValidationError({'due_at': 'The due time must be after the start time.'})

    with transaction.atomic():
        item = lock_equipment(equipment.pk)
        if not item.is_active:
            raise ValidationError({'equipment': 'This item has been retired and cannot be reserved.'})
        if item.condition == Condition.NEEDS_REPAIR:
            raise ValidationError({'equipment': 'This item is waiting for repair and cannot be reserved.'})
        if due_at - start_at > timedelta(days=item.max_loan_days):
            days = item.max_loan_days
            raise ValidationError({'due_at': f'{item.name} can be borrowed for at most {days} day{"s" if days != 1 else ""}.'})
        if Reservation.objects.filter(equipment=item).blocking(start_at, due_at, now).exists():
            raise ValidationError({'equipment': 'This item is already reserved for part of that time.'})

        # Lock the student too, so two bookings at once can't both slip under the limit.
        student = get_user_model().objects.select_for_update().get(pk=student.pk)
        if Reservation.objects.filter(student=student).overdue(now).exists():
            raise ValidationError({
                'student': f'{student.full_name} has overdue equipment and cannot reserve more until it is returned.'
            })
        limit = max_active_reservations()
        if Reservation.objects.filter(student=student).active().count() >= limit:
            raise ValidationError({
                'student': f'Students can have at most {limit} active reservations. Cancel or return one first.'
            })

        return Reservation.objects.create(
            student=student, equipment=item, start_at=start_at, due_at=due_at, notes=notes
        )


def _locked_reservation(reservation):
    item = lock_equipment(reservation.equipment_id)
    locked = Reservation.objects.select_for_update().select_related('student').get(pk=reservation.pk)
    locked.equipment = item
    return locked


def check_out(reservation, *, staff, now=None):
    """Hand a reserved item to the student (desk staff only)."""
    now = now or timezone.now()
    with transaction.atomic():
        reservation = _locked_reservation(reservation)
        item = reservation.equipment
        if reservation.status != Reservation.Status.RESERVED:
            raise ValidationError({
                'status': f'Only reserved items can be checked out; this one is {reservation.get_status_display().lower()}.'
            })
        if timezone.localdate(reservation.start_at) > timezone.localdate(now):
            raise ValidationError({
                'start_at': f'This reservation starts on {timezone.localdate(reservation.start_at):%d %b %Y}; '
                            'it cannot be collected before then.'
            })
        if reservation.due_at <= now:
            raise ValidationError({'due_at': 'This reservation was due back already; cancel it and book again.'})
        if not item.is_reservable:
            raise ValidationError({'equipment': 'This item is retired or waiting for repair and cannot be lent out.'})
        if Reservation.objects.filter(equipment=item, status=Reservation.Status.CHECKED_OUT).exists():
            raise ValidationError({'equipment': 'This item has not been returned from its previous loan yet.'})

        reservation.status = Reservation.Status.CHECKED_OUT
        reservation.checked_out_at = now
        reservation.checked_out_by = staff
        reservation.save(update_fields=['status', 'checked_out_at', 'checked_out_by'])
        return reservation


def return_item(reservation, *, staff, return_condition, notes='', now=None):
    """Take a checked-out item back, recording its condition on the reservation and on the item."""
    now = now or timezone.now()
    if return_condition not in Condition.values:
        raise ValidationError({'return_condition': f'Choose one of: {", ".join(Condition.values)}.'})
    with transaction.atomic():
        reservation = _locked_reservation(reservation)
        if reservation.status != Reservation.Status.CHECKED_OUT:
            raise ValidationError({
                'status': f'Only checked-out items can be returned; this one is {reservation.get_status_display().lower()}.'
            })
        reservation.status = Reservation.Status.RETURNED
        reservation.returned_at = now
        reservation.returned_by = staff
        reservation.return_condition = return_condition
        if notes:
            reservation.notes = f'{reservation.notes}\n{notes}'.strip()
        reservation.save(update_fields=['status', 'returned_at', 'returned_by', 'return_condition', 'notes'])

        item = reservation.equipment
        item.condition = return_condition
        item.save(update_fields=['condition'])
        return reservation


def cancel(reservation):
    """Cancel a reservation that hasn't been collected yet, freeing the item."""
    with transaction.atomic():
        reservation = _locked_reservation(reservation)
        if reservation.status != Reservation.Status.RESERVED:
            raise ValidationError({
                'status': f'Only reservations that have not been collected can be cancelled; '
                          f'this one is {reservation.get_status_display().lower()}.'
            })
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=['status'])
        return reservation
