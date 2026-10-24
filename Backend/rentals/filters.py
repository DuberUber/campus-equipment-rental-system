from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import serializers

from . import services
from .models import Category, Condition, Equipment, Reservation

MOMENT_HELP = 'ISO 8601 date (a whole local day) or datetime.'


class EquipmentFilter(filters.FilterSet):
    kind = filters.ChoiceFilter(field_name='category__kind', choices=Category.Kind.choices)
    condition = filters.ChoiceFilter(choices=Condition.choices)
    # Applied together in filter_queryset: only items free for the whole range.
    available_from = filters.CharFilter(method='filter_available', label=f'Free from. {MOMENT_HELP}')
    available_to = filters.CharFilter(method='filter_available', label=f'Free until. {MOMENT_HELP}')

    class Meta:
        model = Equipment
        fields = ['category', 'kind', 'location', 'condition', 'is_active', 'available_from', 'available_to']

    def filter_available(self, queryset, name, value):
        return queryset  # needs both bounds, so it runs in filter_queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        start, end = self.form.cleaned_data.get('available_from'), self.form.cleaned_data.get('available_to')
        if not (start or end):
            return queryset
        if not (start and end):
            missing = 'available_to' if start else 'available_from'
            raise serializers.ValidationError({missing: ['Give both available_from and available_to.']})
        try:
            start, end = services.parse_window(start, end, max_length=services.MAX_AVAILABILITY_WINDOW)
        except DjangoValidationError as exc:
            renamed = {f'available_{key}': messages for key, messages in exc.message_dict.items()}
            raise serializers.ValidationError(renamed)
        return services.available_equipment(queryset, start, end)


class ReservationFilter(filters.FilterSet):
    when = filters.ChoiceFilter(
        choices=[('current', 'Current'), ('upcoming', 'Upcoming'), ('past', 'Past')], method='filter_when',
        label='current: checked out or inside its window; upcoming: reserved for later; past: finished.',
    )
    overdue = filters.BooleanFilter(field_name='is_overdue', label='Checked out and past the due time.')
    kind = filters.ChoiceFilter(field_name='equipment__category__kind', choices=Category.Kind.choices)
    start_after = filters.IsoDateTimeFilter(field_name='start_at', lookup_expr='gte')
    start_before = filters.IsoDateTimeFilter(field_name='start_at', lookup_expr='lt')
    due_after = filters.IsoDateTimeFilter(field_name='due_at', lookup_expr='gte')
    due_before = filters.IsoDateTimeFilter(field_name='due_at', lookup_expr='lt')

    class Meta:
        model = Reservation
        fields = ['status', 'equipment', 'student', 'when', 'overdue', 'kind']

    def filter_when(self, queryset, name, value):
        now = timezone.now()
        return {'current': queryset.current, 'upcoming': queryset.upcoming, 'past': queryset.past}[value](now)
