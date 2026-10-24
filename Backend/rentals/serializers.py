from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.serializers import StudentSerializer

from . import services
from .models import Category, Condition, Equipment, Location, Reservation


def as_api_error(exc):
    """A services ValidationError as the 400 response DRF would give for a serializer error."""
    return serializers.ValidationError(serializers.as_serializer_error(exc))


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'kind']


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'building']


class EquipmentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    kind = serializers.CharField(source='category.kind', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    building = serializers.CharField(source='location.building', read_only=True)
    is_reservable = serializers.BooleanField(read_only=True)
    # Annotated by the viewset: whether the item is out with a student right now.
    is_checked_out = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Equipment
        fields = [
            'id', 'name', 'category', 'category_name', 'kind', 'location', 'location_name', 'building', 'asset_tag',
            'description', 'condition', 'is_active', 'max_loan_days', 'is_reservable', 'is_checked_out',
        ]

    def validate_asset_tag(self, asset_tag):
        asset_tag = asset_tag.strip().upper()
        if Equipment.objects.filter(asset_tag__iexact=asset_tag).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError('Another item already has this asset tag.')
        return asset_tag


class BusyRangeSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=Reservation.Status.choices)
    is_overdue = serializers.BooleanField(help_text='Overdue items stay busy until returned, so end_at is the end of the window.')


class ReservationSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_staff=False), required=False,
        help_text='Staff only: the student to reserve for. Students always reserve for themselves.',
    )
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_number = serializers.CharField(source='student.student_number', read_only=True, default=None)
    student_email = serializers.EmailField(source='student.email', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    asset_tag = serializers.CharField(source='equipment.asset_tag', read_only=True)
    kind = serializers.CharField(source='equipment.category.kind', read_only=True)
    category_name = serializers.CharField(source='equipment.category.name', read_only=True)
    location_name = serializers.CharField(source='equipment.location.name', read_only=True)
    building = serializers.CharField(source='equipment.location.building', read_only=True)
    checked_out_by_name = serializers.CharField(source='checked_out_by.full_name', read_only=True, default=None)
    returned_by_name = serializers.CharField(source='returned_by.full_name', read_only=True, default=None)
    is_overdue = serializers.SerializerMethodField()
    returned_late = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            'id', 'student', 'student_name', 'student_number', 'student_email', 'equipment', 'equipment_name',
            'asset_tag', 'kind', 'category_name', 'location_name', 'building', 'start_at', 'due_at', 'status',
            'checked_out_at', 'checked_out_by_name', 'returned_at', 'returned_by_name', 'return_condition',
            'notes', 'is_overdue', 'returned_late', 'created_at',
        ]
        read_only_fields = ['status', 'checked_out_at', 'returned_at', 'return_condition', 'created_at']

    # Querysets annotate both flags (ReservationQuerySet.with_flags); fresh instances compute them.
    def get_is_overdue(self, reservation) -> bool:
        flag = getattr(reservation, 'is_overdue', None)
        return reservation.compute_overdue() if flag is None else flag

    def get_returned_late(self, reservation) -> bool:
        flag = getattr(reservation, 'returned_late', None)
        return reservation.compute_returned_late() if flag is None else flag

    def validate(self, attrs):
        user = self.context['request'].user
        if user.is_staff:
            if 'student' not in attrs:
                raise serializers.ValidationError({'student': 'Choose the student this reservation is for.'})
        elif attrs.setdefault('student', user) != user:
            raise serializers.ValidationError({'student': 'You can only reserve equipment for yourself.'})
        return attrs

    def create(self, validated_data):
        try:
            return services.create_reservation(**validated_data)
        except DjangoValidationError as exc:
            raise as_api_error(exc)


class ReturnSerializer(serializers.Serializer):
    return_condition = serializers.ChoiceField(choices=Condition.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class StudentSummarySerializer(StudentSerializer):
    """A student in the staff directory, with their current load (annotated by the viewset)."""

    active_reservations = serializers.IntegerField(read_only=True, default=0)
    overdue_reservations = serializers.IntegerField(read_only=True, default=0)

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + ['active_reservations', 'overdue_reservations']
