import csv
import math

from django.core.management.base import BaseCommand
from django.utils import timezone

from rentals.models import Reservation


class Command(BaseCommand):
    help = (
        'List overdue equipment: items still checked out after their due time. Read-only and '
        'non-interactive, so it is safe to run from cron (use --exit-code to alert when anything is overdue).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['text', 'csv'], default='text', help='Output format (default text).')
        parser.add_argument(
            '--exit-code', action='store_true', help='Exit with status 1 when at least one item is overdue.'
        )

    def handle(self, *args, **options):
        now = timezone.now()
        overdue = list(
            Reservation.objects.overdue(now).select_related('equipment__location', 'student').order_by('due_at')
        )
        if options['format'] == 'csv':
            self.write_csv(overdue, now)
        else:
            self.write_text(overdue, now)
        if options['exit_code'] and overdue:
            raise SystemExit(1)

    @staticmethod
    def days_late(reservation, now):
        """Started days since the due time, so anything overdue is at least one day late."""
        return max(1, math.ceil((now - reservation.due_at).total_seconds() / 86400))

    def write_text(self, overdue, now):
        if not overdue:
            self.stdout.write(self.style.SUCCESS('No overdue equipment.'))
            return
        self.stdout.write(self.style.WARNING(f'{len(overdue)} overdue item{"s" if len(overdue) != 1 else ""}:'))
        for reservation in overdue:
            student, item = reservation.student, reservation.equipment
            due = timezone.localtime(reservation.due_at)
            self.stdout.write(
                f'  {item.asset_tag:<10} {item.name:<28} {student.full_name} ({student.student_number or student.username}), '
                f'due {due:%Y-%m-%d %H:%M}, {self.days_late(reservation, now)} day(s) late, return to {item.location.name}'
            )

    def write_csv(self, overdue, now):
        writer = csv.writer(self.stdout)
        writer.writerow(['reservation', 'asset_tag', 'equipment', 'student', 'student_number', 'email', 'due_at', 'days_late'])
        for reservation in overdue:
            student, item = reservation.student, reservation.equipment
            writer.writerow([
                reservation.pk, item.asset_tag, item.name, student.full_name, student.student_number or '',
                student.email, reservation.due_at.isoformat(), self.days_late(reservation, now),
            ])
