from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, mixins, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .filters import EquipmentFilter, ReservationFilter
from .models import Category, Equipment, Location, Reservation
from .permissions import IsDeskStaff, IsStaffOrReadOnly, IsStudent, ReservationPermission
from .serializers import (
    BusyRangeSerializer,
    CategorySerializer,
    EquipmentSerializer,
    LocationSerializer,
    ReservationSerializer,
    ReturnSerializer,
    StudentSummarySerializer,
    as_api_error,
)


def reservations_with_details():
    """Reservations with everything ReservationSerializer reads, in one query."""
    return Reservation.objects.select_related(
        'student', 'equipment__category', 'equipment__location', 'checked_out_by', 'returned_by'
    ).with_flags()


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['kind', 'slug']
    search_fields = ['name']
    ordering_fields = ['name', 'kind']


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffOrReadOnly]
    filterset_fields = ['building']
    search_fields = ['name', 'building']
    ordering_fields = ['name', 'building']


class EquipmentViewSet(viewsets.ModelViewSet):
    """The equipment catalogue: everyone signed in browses it, desk staff maintain it."""

    serializer_class = EquipmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffOrReadOnly]
    filterset_class = EquipmentFilter
    search_fields = ['name', 'asset_tag']
    ordering_fields = ['name', 'asset_tag', 'condition', 'max_loan_days']
    ordering = ['name', 'asset_tag']

    def get_queryset(self):
        checked_out = Reservation.objects.filter(equipment=OuterRef('pk'), status=Reservation.Status.CHECKED_OUT)
        queryset = Equipment.objects.select_related('category', 'location').annotate(is_checked_out=Exists(checked_out))
        # Retired items stay in the catalogue for staff (and in rental history) but not for students.
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter('from', str, description='Window start: ISO date or datetime (default: today).'),
            OpenApiParameter('to', str, description='Window end: ISO date (inclusive) or datetime (default: 28 days on).'),
        ],
        responses=inline_serializer('EquipmentAvailability', {
            'equipment': serializers.IntegerField(),
            'from': serializers.DateTimeField(),
            'to': serializers.DateTimeField(),
            'is_reservable': serializers.BooleanField(help_text='False for retired items and items waiting for repair.'),
            'is_available': serializers.BooleanField(help_text='Reservable and free for the whole window.'),
            'busy': BusyRangeSerializer(many=True),
        }),
    )
    @action(detail=True)
    def availability(self, request, pk=None):
        """When the item is busy between ``from`` and ``to`` (at most 120 days). Borrowers are not shown."""
        item = self.get_object()
        try:
            start, end = services.parse_window(
                request.query_params.get('from'), request.query_params.get('to'),
                default_length=services.DEFAULT_AVAILABILITY_WINDOW, max_length=services.MAX_AVAILABILITY_WINDOW,
            )
        except DjangoValidationError as exc:
            raise as_api_error(exc)
        busy = services.busy_ranges(item, start, end)
        moment = serializers.DateTimeField()
        return Response({
            'equipment': item.pk,
            'from': moment.to_representation(start),
            'to': moment.to_representation(end),
            'is_reservable': item.is_reservable,
            'is_available': item.is_reservable and not busy,
            'busy': BusyRangeSerializer(busy, many=True).data,
        })


class ReservationViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """Students see and manage their own reservations; desk staff see all of them and check items in and out.

    Reservations are never edited or deleted: they move through reserved -> checked_out -> returned
    (or cancelled) with the actions below, which keeps the rental history intact.
    """

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated, ReservationPermission]
    filterset_class = ReservationFilter
    search_fields = [
        'equipment__name', 'equipment__asset_tag', 'student__first_name', 'student__last_name',
        'student__student_number',
    ]
    ordering_fields = ['start_at', 'due_at', 'created_at', 'status']

    def get_queryset(self):
        queryset = reservations_with_details()
        if getattr(self, 'swagger_fake_view', False):  # OpenAPI schema generation has no real user
            return queryset.none()
        if not self.request.user.is_staff:
            queryset = queryset.filter(student=self.request.user)
        return queryset

    def respond_with(self, reservation):
        """The reservation as stored, re-read with its annotations."""
        return Response(self.get_serializer(self.get_queryset().get(pk=reservation.pk)).data)

    @extend_schema(request=None, responses=ReservationSerializer)
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsDeskStaff])
    def checkout(self, request, pk=None):
        """Hand the item to the student (staff). Allowed from the reservation's start day until it is due."""
        try:
            reservation = services.check_out(self.get_object(), staff=request.user)
        except DjangoValidationError as exc:
            raise as_api_error(exc)
        return self.respond_with(reservation)

    @extend_schema(request=ReturnSerializer, responses=ReservationSerializer)
    @action(
        detail=True, methods=['post'], url_path='return', url_name='return',
        permission_classes=[permissions.IsAuthenticated, IsDeskStaff],
    )
    def return_item(self, request, pk=None):
        """Take the item back (staff). ``return_condition`` also becomes the item's condition."""
        reservation = self.get_object()
        details = ReturnSerializer(data=request.data)
        details.is_valid(raise_exception=True)
        try:
            reservation = services.return_item(reservation, staff=request.user, **details.validated_data)
        except DjangoValidationError as exc:
            raise as_api_error(exc)
        return self.respond_with(reservation)

    @extend_schema(request=None, responses=ReservationSerializer)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a reservation that hasn't been collected. Students can cancel their own."""
        try:
            reservation = services.cancel(self.get_object())
        except DjangoValidationError as exc:
            raise as_api_error(exc)
        return self.respond_with(reservation)

    @action(detail=False, permission_classes=[permissions.IsAuthenticated, IsDeskStaff])
    def overdue(self, request):
        """Items still checked out after their due time, longest overdue first (staff)."""
        queryset = self.filter_queryset(self.get_queryset().filter(is_overdue=True)).order_by('due_at', 'pk')
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """Student directory for desk staff, with each student's active and overdue reservation counts."""

    serializer_class = StudentSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsDeskStaff]
    filterset_fields = ['course', 'year', 'student_number']
    search_fields = ['first_name', 'last_name', 'email', 'student_number', 'username', 'course']
    ordering_fields = ['last_name', 'first_name', 'student_number', 'year', 'overdue_reservations']

    def get_queryset(self):
        return get_user_model().objects.filter(is_staff=False).annotate(
            active_reservations=Count(
                'reservations', filter=Q(reservations__status__in=Reservation.ACTIVE_STATUSES), distinct=True
            ),
            overdue_reservations=Count(
                'reservations',
                filter=Q(reservations__status=Reservation.Status.CHECKED_OUT, reservations__due_at__lt=timezone.now()),
                distinct=True,
            ),
        ).order_by('last_name', 'first_name', 'username')  # aggregate queries skip Meta.ordering


class HistoryView(generics.ListAPIView):
    """A student's rental history, newest first. Filters as /api/reservations/ (status, when, overdue, ...)."""

    serializer_class = ReservationSerializer
    filterset_class = ReservationFilter
    search_fields = ['equipment__name', 'equipment__asset_tag']
    ordering_fields = ['start_at', 'due_at', 'created_at', 'status']
    ordering = ['-start_at', '-pk']

    def get_student(self):
        raise NotImplementedError

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Reservation.objects.none()
        return reservations_with_details().filter(student=self.get_student())


class MyHistoryView(HistoryView):
    """The signed-in student's own rental history."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_student(self):
        return self.request.user


class StudentHistoryView(HistoryView):
    """Any student's rental history (staff)."""

    permission_classes = [permissions.IsAuthenticated, IsDeskStaff]

    def get_student(self):
        return get_object_or_404(get_user_model(), pk=self.kwargs['pk'], is_staff=False)
