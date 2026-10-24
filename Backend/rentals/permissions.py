"""Who may see and change what.

There are two roles: students (any account without ``is_staff``) and desk staff (``is_staff``). List
endpoints are scoped in ``get_queryset``, so students only ever see their own reservations; these classes
guard the role-specific endpoints and writes.
"""
from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    message = 'Only student accounts can use this endpoint.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not request.user.is_staff)


class IsDeskStaff(permissions.BasePermission):
    message = 'Only equipment desk staff can do this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsStaffOrReadOnly(permissions.BasePermission):
    """Catalogue data (categories, locations, equipment): anyone signed in reads, staff write."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or bool(request.user and request.user.is_staff)


class ReservationPermission(permissions.BasePermission):
    """Students reserve and cancel their own reservations; staff do everything, including check-out and return."""

    def has_object_permission(self, request, view, reservation):
        if request.user.is_staff:
            return True
        if request.method in permissions.SAFE_METHODS or view.action == 'cancel':
            return reservation.student_id == request.user.pk
        return False
