import secrets
from datetime import datetime, time, timedelta

from decouple import config
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from rentals.models import Category, Equipment, Location, Reservation

DEMO_USERS = [
    # username, role, description
    ('admin', 'superuser', 'superuser: Django admin + every API endpoint'),
    ('desk', 'staff', 'staff: equipment desk, check-outs and returns, overdue list, students'),
    ('aoife', 'student', 'student: browse, reserve and track rentals'),
    ('liam', 'student', 'student with an overdue item (blocked from reserving)'),
]

# username: first name, last name, student number, course, year. aoife and liam are demo accounts; the others
# are sample students who can't sign in (no usable password).
STUDENTS = {
    'aoife': ('Aoife', 'Brennan', 'S21000101', 'BSc Physics', 3),
    'liam': ('Liam', 'Walsh', 'S22000202', 'BEng Mechanical Engineering', 2),
    'niamh': ('Niamh', 'Doyle', 'S23000303', 'BSc Biology', 1),
    'ciaran': ('Ciaran', "O'Neill", 'S20000404', 'BA Sports Science', 4),
    'emma': ('Emma', 'Ryan', 'S24000505', 'BSc Computer Science', 1),
    'oisin': ('Oisin', 'Murphy', 'S22000606', 'BA Media Studies', 2),
}

LOCATIONS = [
    ('Engineering Equipment Desk', 'Engineering Building'),
    ('Science Stores', 'Science Building'),
    ('Media Loans Desk', 'Library'),
    ('Sports Centre Desk', 'Sports Centre'),
    ('Pavilion Store', 'Sports Pavilion'),
]

CATEGORIES = [
    ('Electronics', 'electronics', Category.Kind.LAB),
    ('Microscopy', 'microscopy', Category.Kind.LAB),
    ('Photography', 'photography', Category.Kind.LAB),
    ('Field sports', 'field-sports', Category.Kind.SPORTS),
    ('Racket sports', 'racket-sports', Category.Kind.SPORTS),
    ('Training gear', 'training-gear', Category.Kind.SPORTS),
]

# asset tag, name, category slug, location index, max loan days, condition, description[, is_active]
EQUIPMENT = [
    ('OSC-001', 'Oscilloscope, 100 MHz 2-channel', 'electronics', 0, 7, 'good',
     'Bench digital storage oscilloscope with two 10x probes and a USB cable for screen captures.'),
    ('OSC-002', 'Oscilloscope, 100 MHz 2-channel', 'electronics', 0, 7, 'excellent',
     'Bench digital storage oscilloscope with two 10x probes and a USB cable for screen captures.'),
    ('MM-001', 'Digital multimeter', 'electronics', 0, 14, 'good', 'Auto-ranging multimeter with test leads and crocodile clips.'),
    ('MM-002', 'Digital multimeter', 'electronics', 0, 14, 'good', 'Auto-ranging multimeter with test leads and crocodile clips.'),
    ('MM-003', 'Digital multimeter', 'electronics', 0, 14, 'fair', 'Auto-ranging multimeter. The case is scratched but it reads accurately.'),
    ('RPI-001', 'Raspberry Pi 5 starter kit', 'electronics', 0, 14, 'excellent',
     'Raspberry Pi 5 (8 GB), power supply, 64 GB card with the OS, case, breadboard and jumper wires.'),
    ('RPI-002', 'Raspberry Pi 5 starter kit', 'electronics', 0, 14, 'good',
     'Raspberry Pi 5 (8 GB), power supply, 64 GB card with the OS, case, breadboard and jumper wires.'),
    ('RPI-003', 'Raspberry Pi 5 starter kit', 'electronics', 0, 14, 'good',
     'Raspberry Pi 5 (8 GB), power supply, 64 GB card with the OS, case, breadboard and jumper wires.'),
    ('MIC-001', 'Compound microscope', 'microscopy', 1, 5, 'excellent', '40x-1000x binocular microscope with LED lighting and slides.'),
    ('MIC-002', 'Compound microscope', 'microscopy', 1, 5, 'needs_repair', 'Fine focus is slipping; waiting for a service.'),
    ('CAM-001', 'DSLR camera with 18-55 mm lens', 'photography', 2, 3, 'good', 'Camera body, kit lens, two batteries, charger and a 64 GB card.'),
    ('CAM-002', 'DSLR camera with 18-55 mm lens', 'photography', 2, 3, 'excellent', 'Camera body, kit lens, two batteries, charger and a 64 GB card.'),
    ('FB-001', 'Size 5 football', 'field-sports', 3, 2, 'good', 'Match football, inflated and ready to play.'),
    ('FB-002', 'Size 5 football', 'field-sports', 3, 2, 'good', 'Match football, inflated and ready to play.'),
    ('FB-003', 'Size 5 football', 'field-sports', 3, 2, 'fair', 'Training football. Some wear on the panels.'),
    ('TR-001', 'Tennis racket', 'racket-sports', 3, 2, 'excellent', 'Adult racket with a cover. Balls are available at the desk.'),
    ('TR-002', 'Tennis racket', 'racket-sports', 3, 2, 'good', 'Adult racket with a cover. Balls are available at the desk.'),
    ('HUR-001', 'Hurley (34 inch)', 'field-sports', 4, 3, 'good', 'Ash hurley with a grip and a bas band.'),
    ('HUR-002', 'Hurley (32 inch)', 'field-sports', 4, 3, 'excellent', 'Ash hurley with a grip and a bas band.'),
    ('HUR-003', 'Hurley (34 inch)', 'field-sports', 4, 3, 'fair', 'Retired after the bas cracked.', False),
    ('BIB-001', 'Training bibs (set of 12)', 'training-gear', 4, 2, 'good', 'Twelve mesh bibs in orange, washed after every loan.'),
    ('BIB-002', 'Training bibs (set of 12)', 'training-gear', 4, 2, 'good', 'Twelve mesh bibs in blue, washed after every loan.'),
    ('CON-001', 'Training cones (set of 20)', 'training-gear', 4, 2, 'excellent', 'Twenty marker cones in a carry bag.'),
    ('CON-002', 'Training cones (set of 20)', 'training-gear', 4, 2, 'good', 'Twenty marker cones in a carry bag.'),
]

# Times are (days from today, hour), in TIME_ZONE. Reservations: student, asset tag, start, due, status,
# checked out at, returned at, return condition, notes.
RESERVATIONS = [
    ('aoife', 'OSC-001', (-20, 9), (-17, 17), 'returned', (-20, 10), (-17, 16), 'good', 'Signals lab practical.'),
    ('aoife', 'CAM-001', (-12, 9), (-10, 17), 'returned', (-12, 9), (-9, 11), 'good', 'Field trip photos.'),
    ('aoife', 'RPI-001', (-1, 9), (2, 17), 'checked_out', (-1, 10), None, '', 'Final-year project prototype.'),
    ('aoife', 'TR-001', (3, 9), (4, 17), 'reserved', None, None, '', ''),
    ('liam', 'FB-001', (-15, 9), (-14, 17), 'returned', (-15, 12), (-14, 15), 'good', 'Five-a-side.'),
    ('liam', 'MM-001', (-6, 9), (-2, 17), 'checked_out', (-6, 10), None, '', 'Circuits lab.'),
    ('niamh', 'MIC-001', (-5, 9), (-1, 17), 'checked_out', (-5, 9), None, '', 'Cell biology assignment.'),
    ('ciaran', 'HUR-001', (-2, 9), (0, 17), 'checked_out', (-2, 11), None, '', 'Club training.'),
    ('ciaran', 'TR-002', (-8, 9), (-7, 17), 'returned', (-8, 10), (-6, 10), 'fair', 'Strings fraying on return.'),
    ('emma', 'OSC-002', (0, 9), (2, 17), 'reserved', None, None, '', 'Embedded systems lab.'),
    ('emma', 'BIB-001', (1, 9), (2, 17), 'reserved', None, None, '', 'Society training session.'),
    ('oisin', 'CON-001', (-3, 9), (-2, 17), 'cancelled', None, None, '', 'Session called off.'),
]


def at(offset):
    """An aware datetime ``days`` from today at ``hour`` o'clock, local time."""
    days, hour = offset
    return timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=days), time(hour)))


class Command(BaseCommand):
    help = (
        'Create demo accounts (superuser "admin", desk staff "desk", students "aoife" and "liam") plus sample '
        'categories, locations, lab and sports equipment, students and reservations (returned, current, '
        'upcoming and overdue). Passwords are generated on every run (or taken from DEMO_PASSWORD in the '
        'environment or Backend/.env) and printed to the console only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all equipment, reservations and student accounts before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.reset()

        credentials = self.create_demo_users()
        if Equipment.objects.exists() or Reservation.objects.exists():
            self.stdout.write(self.style.WARNING(
                'Equipment data already exists; skipping sample records (use --reset to rebuild them).'
            ))
        else:
            self.create_sample_records()

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Demo accounts'))
        for username, password, description in credentials:
            self.stdout.write(f'  {username:<10} {password:<20} ({description})')
        self.stdout.write('These passwords are not stored anywhere else; re-run this command to rotate them.')
        self.stdout.write(
            'Sign in to the React app as aoife or liam (students) or desk (staff); use admin for the Django admin.'
        )

    def reset(self):
        # Reservations first: equipment, categories, locations and students are protected from cascading deletes.
        for model in (Reservation, Equipment, Category, Location):
            model.objects.all().delete()
        # Student accounts go too; staff accounts are kept (their passwords are reset below).
        get_user_model().objects.filter(is_staff=False).delete()
        self.stdout.write('Removed existing equipment, reservations and student accounts.')

    def create_demo_users(self):
        User = get_user_model()
        shared_password = config('DEMO_PASSWORD', default='')
        credentials = []
        for username, role, description in DEMO_USERS:
            password = shared_password or secrets.token_urlsafe(12)
            user, _ = User.objects.get_or_create(username=username, defaults={'email': f'{username}@campus.example.com'})
            user.is_staff = role in ('superuser', 'staff')
            user.is_superuser = role == 'superuser'
            if role == 'student':
                self.fill_student(user, username)
            elif role == 'staff':
                user.first_name, user.last_name = 'Equipment', 'Desk'
            user.set_password(password)
            user.save()
            credentials.append((username, password, description))
        return credentials

    @staticmethod
    def fill_student(user, username):
        user.first_name, user.last_name, user.student_number, user.course, user.year = STUDENTS[username]
        user.email = f'{username}@student.campus.example.com'

    def create_sample_records(self):
        User = get_user_model()
        locations = [Location.objects.create(name=name, building=building) for name, building in LOCATIONS]
        categories = {slug: Category.objects.create(name=name, slug=slug, kind=kind) for name, slug, kind in CATEGORIES}
        equipment = {}
        for tag, name, slug, location, max_days, condition, description, *active in EQUIPMENT:
            equipment[tag] = Equipment.objects.create(
                asset_tag=tag, name=name, category=categories[slug], location=locations[location],
                max_loan_days=max_days, condition=condition, description=description,
                is_active=active[0] if active else True,
            )

        students = {user.username: user for user in User.objects.filter(username__in=STUDENTS)}
        for username in STUDENTS:
            if username not in students:
                student = User(username=username)
                self.fill_student(student, username)
                student.set_unusable_password()
                student.save()
                students[username] = student

        desk = User.objects.get(username='desk')
        for username, tag, start, due, status, checked_out, returned, condition, notes in RESERVATIONS:
            # Historical records are written directly: the booking rules only accept reservations from now on.
            Reservation.objects.create(
                student=students[username], equipment=equipment[tag], start_at=at(start), due_at=at(due),
                status=status, notes=notes,
                checked_out_at=at(checked_out) if checked_out else None,
                checked_out_by=desk if checked_out else None,
                returned_at=at(returned) if returned else None,
                returned_by=desk if returned else None,
                return_condition=condition,
            )
            if condition:
                Equipment.objects.filter(pk=equipment[tag].pk).update(condition=condition)

        overdue = Reservation.objects.overdue().count()
        self.stdout.write(self.style.SUCCESS(
            f'Created {len(locations)} locations, {len(categories)} categories, {len(equipment)} items of equipment, '
            f'{len(students)} students and {Reservation.objects.count()} reservations ({overdue} overdue).'
        ))
