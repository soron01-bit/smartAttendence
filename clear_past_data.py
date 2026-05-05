import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from attendance.models import Attendance, SubjectPermission

def clear_past_data():
    now = timezone.localtime(timezone.now())
    today = now.date()
    
    # Count before
    att_count = Attendance.objects.filter(timestamp__date__lt=today).count()
    perm_count = SubjectPermission.objects.filter(date__lt=today).count()
    
    print(f"Found {att_count} past attendances and {perm_count} past permissions.")
    
    # Delete
    Attendance.objects.filter(timestamp__date__lt=today).delete()
    SubjectPermission.objects.filter(date__lt=today).delete()
    
    print("Deleted successfully.Recounting starts from today.")

if __name__ == "__main__":
    clear_past_data()
