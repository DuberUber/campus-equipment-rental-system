from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    class Kind(models.TextChoices):
        LAB = 'lab', 'Lab'
        SPORTS = 'sports', 'Sports'

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)

    class Meta:
        ordering = ['kind', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Location(models.Model):
    """An equipment desk or store where items are collected and returned."""

    name = models.CharField(max_length=120, unique=True)
    building = models.CharField(max_length=120)

    class Meta:
        ordering = ['building', 'name']

    def __str__(self):
        return f'{self.name} ({self.building})'


class Condition(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    GOOD = 'good', 'Good'
    FAIR = 'fair', 'Fair'
    NEEDS_REPAIR = 'needs_repair', 'Needs repair'


class Equipment(models.Model):
    # PROTECT: an item's category and location can't vanish from under it (or its rental history).
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='equipment')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='equipment')
    asset_tag = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)
    condition = models.CharField(max_length=12, choices=Condition.choices, default=Condition.GOOD)
    is_active = models.BooleanField(default=True, help_text='Inactive items are retired and cannot be reserved.')
    max_loan_days = models.PositiveSmallIntegerField(
        default=7, validators=[MinValueValidator(1), MaxValueValidator(90)],
        help_text='Longest reservation allowed for this item, in days.',
    )

    class Meta:
        ordering = ['name', 'asset_tag']
        verbose_name_plural = 'equipment'
        indexes = [
            # The browse page lists one category at a time in name order.
            models.Index(fields=['category', 'name'], name='equipment_category_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.asset_tag})'

    @property
    def is_reservable(self) -> bool:
        return self.is_active and self.condition != Condition.NEEDS_REPAIR


class ReservationQuerySet(models.QuerySet):
    def active(self):
        """Reservations that hold the item: reserved or checked out."""
        return self.filter(status__in=Reservation.ACTIVE_STATUSES)

    def blocking(self, start, end, now=None):
        """Active reservations that keep their item busy at some point in [start, end).

        A reservation holds the item for [start_at, due_at). An overdue item hasn't come back, so it stays
        busy until it is returned, whatever its due time says.
        """
        now = now or timezone.now()
        return self.active().filter(start_at__lt=end).filter(
            models.Q(due_at__gt=start) | models.Q(status=Reservation.Status.CHECKED_OUT, due_at__lt=now)
        )

    def overdue(self, now=None):
        """Checked out and past the due time. Computed on every query, never stored."""
        return self.filter(status=Reservation.Status.CHECKED_OUT, due_at__lt=now or timezone.now())

    def with_flags(self, now=None):
        """Annotate ``is_overdue`` and ``returned_late`` (returned after it was due)."""
        now = now or timezone.now()
        return self.annotate(
            is_overdue=models.Case(
                models.When(status=Reservation.Status.CHECKED_OUT, due_at__lt=now, then=models.Value(True)),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
            returned_late=models.Case(
                models.When(returned_at__gt=models.F('due_at'), then=models.Value(True)),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
        )

    def current(self, now=None):
        """Out with the student, or reserved and inside its window (waiting to be collected)."""
        now = now or timezone.now()
        return self.filter(
            models.Q(status=Reservation.Status.CHECKED_OUT)
            | models.Q(status=Reservation.Status.RESERVED, start_at__lte=now, due_at__gt=now)
        )

    def upcoming(self, now=None):
        return self.filter(status=Reservation.Status.RESERVED, start_at__gt=now or timezone.now())

    def past(self, now=None):
        """Finished: returned, cancelled, or reserved but never collected before it was due."""
        now = now or timezone.now()
        return self.filter(
            models.Q(status__in=[Reservation.Status.RETURNED, Reservation.Status.CANCELLED])
            | models.Q(status=Reservation.Status.RESERVED, due_at__lte=now)
        )


class Reservation(models.Model):
    """A student's booking of one item: reserved -> checked_out -> returned, or cancelled before checkout."""

    class Status(models.TextChoices):
        RESERVED = 'reserved', 'Reserved'
        CHECKED_OUT = 'checked_out', 'Checked out'
        RETURNED = 'returned', 'Returned'
        CANCELLED = 'cancelled', 'Cancelled'

    ACTIVE_STATUSES = (Status.RESERVED, Status.CHECKED_OUT)

    # PROTECT: rental history must survive deleting a student account or retiring an item.
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reservations')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='reservations')
    start_at = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESERVED)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    return_condition = models.CharField(max_length=12, choices=Condition.choices, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        ordering = ['-start_at', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(due_at__gt=models.F('start_at')),
                name='reservation_due_after_start',
                violation_error_message='The due time must be after the start time.',
            ),
        ]
        indexes = [
            # Availability: one item's reservations in a date range.
            models.Index(fields=['equipment', 'start_at'], name='reservation_equipment_idx'),
            # Rental history: one student's reservations in date order.
            models.Index(fields=['student', 'start_at'], name='reservation_student_idx'),
            # The overdue list (status = checked_out, due_at < now) and the desk's pickups and returns.
            models.Index(fields=['status', 'due_at'], name='reservation_status_due_idx'),
        ]

    def __str__(self):
        return f'{self.equipment} for {self.student} from {self.start_at:%Y-%m-%d %H:%M}'

    def compute_overdue(self, now=None) -> bool:
        """Same rule as the ``is_overdue`` annotation, for instances loaded without it."""
        return self.status == self.Status.CHECKED_OUT and self.due_at < (now or timezone.now())

    def compute_returned_late(self) -> bool:
        return bool(self.returned_at and self.returned_at > self.due_at)
