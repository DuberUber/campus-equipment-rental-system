from django.contrib import admin

from .models import Category, Equipment, Location, Reservation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'slug']
    list_filter = ['kind']
    search_fields = ['name']
    prepopulated_fields = {'slug': ['name']}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'building']
    search_fields = ['name', 'building']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['asset_tag', 'name', 'category', 'location', 'condition', 'max_loan_days', 'is_active']
    list_filter = ['category__kind', 'category', 'location', 'condition', 'is_active']
    list_select_related = ['category', 'location']
    search_fields = ['name', 'asset_tag']
    autocomplete_fields = ['category', 'location']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'student', 'start_at', 'due_at', 'status', 'is_overdue']
    list_filter = ['status', 'equipment__category__kind']
    list_select_related = ['equipment', 'student']
    search_fields = ['equipment__name', 'equipment__asset_tag', 'student__last_name', 'student__student_number']
    readonly_fields = ['checked_out_at', 'checked_out_by', 'returned_at', 'returned_by', 'created_at']
    date_hierarchy = 'start_at'
    autocomplete_fields = ['student', 'equipment']

    def get_queryset(self, request):
        return super().get_queryset(request).with_flags()

    @admin.display(boolean=True, ordering='is_overdue', description='Overdue')
    def is_overdue(self, reservation):
        return reservation.is_overdue
