import json
import math
import random
import string
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import datetime
from .models import UserProfile, Attendance, Institute, Subject, SubjectPermission

# Dummy configurations (can be moved to settings.py)
MAX_DISTANCE_METERS = 400 # Maximum distance in meters to allow attendance
LATE_CUTOFF_TIME = datetime.time(9, 0, 0)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def index(request):
    return render(request, 'attendance/index.html')

def institute_portal(request):
    return render(request, 'attendance/institute_admin.html')

def register(request):
    return render(request, 'attendance/register.html')

def attendance(request):
    return render(request, 'attendance/attendance.html')

def euclidean_distance(list1, list2):
    if len(list1) != len(list2):
        return 999.0
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(list1, list2)))

@csrf_exempt
def api_register(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get('name')
            role = data.get('role')
            descriptor = data.get('descriptor') # Should be a list of 128 floats
            institute_code = data.get('institute_code')

            if not all([name, role, descriptor, institute_code]) or len(descriptor) != 128:
                return JsonResponse({'success': False, 'message': 'Invalid data provided or missing institute code.'}, status=400)

            try:
                institute = Institute.objects.get(unique_code=institute_code)
            except Institute.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Invalid institute code.'}, status=400)

            department = data.get('department', '')
            year = data.get('year', '')
            semester = data.get('semester', '')
            student_group = data.get('student_group', '')
            roll_number = data.get('roll_number', '')

            # Find closest match to prevent duplicates
            min_dist = float('inf')
            profiles = UserProfile.objects.all()
            for profile in profiles:
                saved_descriptor = json.loads(profile.face_encoding)
                dist = euclidean_distance(descriptor, saved_descriptor)
                if dist < min_dist:
                    min_dist = dist

            if min_dist < 0.5:
                return JsonResponse({'success': False, 'message': 'This face is already registered in the system.'}, status=400)

            # Detailed Profile Fields
            phone_number = data.get('phone_number', '')
            blood_group = data.get('blood_group', '')
            guardian_name = data.get('guardian_name', '')

            # Generate secure random password
            raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            user_profile = UserProfile.objects.create(
                name=name,
                role=role,
                institute=institute,
                department=department,
                year=year,
                semester=semester,
                student_group=student_group,
                roll_number=roll_number,
                phone_number=phone_number,
                blood_group=blood_group,
                guardian_name=guardian_name,
                password=make_password(raw_password),
                face_encoding=json.dumps(descriptor)
            )

            return JsonResponse({
                'success': True,
                'message': f'Successfully registered!',
                'user_id': user_profile.user_id,
                'password': raw_password
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def api_match(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            descriptor = data.get('descriptor')
            lat = data.get('lat')
            lon = data.get('lon')
            
            if not descriptor or len(descriptor) != 128:
                return JsonResponse({'success': False, 'message': 'Invalid descriptor.'}, status=400)

            if lat is None or lon is None:
                return JsonResponse({'success': False, 'message': 'Location tracking is required for attendance.'}, status=400)

            # Load all users
            profiles = UserProfile.objects.all()
            if not profiles.exists():
                return JsonResponse({'success': False, 'message': 'No registered users found in the system.'}, status=404)

            best_match = None
            min_dist = float('inf')

            for profile in profiles:
                saved_descriptor = json.loads(profile.face_encoding)
                dist = euclidean_distance(descriptor, saved_descriptor)
                if dist < min_dist:
                    min_dist = dist
                    best_match = profile

            # Threshold for Euclidean distance with face-api.js SSD is usually ~0.6 with un-normalized descriptors. 
            # 0.55 is a balanced threshold for smooth recognition.
            threshold = 0.55

            # Threshold for Euclidean distance with face-api.js SSD is usually ~0.6 with un-normalized descriptors. 
            # 0.55 is a balanced threshold for smooth recognition.
            threshold = 0.55

            if best_match and min_dist < threshold:
                if not best_match.institute:
                    return JsonResponse({'success': False, 'message': 'User is not linked to any institute.'}, status=400)
                    
                dist_to_school = haversine(float(lat), float(lon), best_match.institute.latitude, best_match.institute.longitude)
                if dist_to_school > MAX_DISTANCE_METERS:
                    return JsonResponse({'success': False, 'message': f'You are too far from your institute. ({int(dist_to_school)}m away)'}, status=400)

                # --- SUBJECT-WISE ATTENDANCE LOGIC ---
                now = timezone.localtime()
                current_time = now.time()
                today = now.date()
                
                # Find active subjects for this student's institute and semester that have permission for today
                active_subject = None
                permitted_subjects = SubjectPermission.objects.filter(
                    date=today,
                    subject__institute=best_match.institute,
                    subject__semester=best_match.semester
                ).select_related('subject')
                
                for perm in permitted_subjects:
                    s = perm.subject
                    if s.start_time and s.end_time:
                        if s.start_time <= current_time <= s.end_time:
                            active_subject = s
                            break
                
                # Check if there was ANY permission today, even if time passed
                has_any_permission_today = permitted_subjects.exists()
                
                if not active_subject:
                    # Check if there is a subject that WAS permitted today but time has passed
                    ended_subject = None
                    for perm in permitted_subjects:
                        if perm.subject.end_time and current_time > perm.subject.end_time:
                            ended_subject = perm.subject
                            break
                    
                    if ended_subject:
                        return JsonResponse({'success': False, 'message': f'The session for {ended_subject.name} has already ended.'}, status=400)
                    
                    return JsonResponse({'success': False, 'message': 'No permitted subject is currently in session for your semester.'}, status=400)

                # Check if attendance already marked for THIS subject today
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + datetime.timedelta(days=1)
                
                if Attendance.objects.filter(user=best_match, subject=active_subject, timestamp__gte=today_start, timestamp__lt=today_end).exists():
                    return JsonResponse({'success': False, 'message': f'Attendance already marked for {active_subject.name} today.'}, status=400)
                
                # Check late entry (using subject's start time + 10 mins buffer or just the fixed cutoff?)
                # Let's use a 10-minute buffer after subject start time for 'Present', otherwise 'Late'
                # Or keep the global LATE_CUTOFF_TIME? The user didn't specify. 
                # Let's make it relative to subject start time if available.
                status = 'Present'
                if active_subject.start_time:
                    # Convert subject start time to a datetime for comparison
                    subject_start_dt = now.replace(hour=active_subject.start_time.hour, minute=active_subject.start_time.minute, second=0, microsecond=0)
                    late_threshold = subject_start_dt + datetime.timedelta(minutes=10)
                    if now > late_threshold:
                        status = 'Late'
                
                # Mark attendance
                record = Attendance.objects.create(user=best_match, subject=active_subject, status=status)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Attendance marked: {status} for {active_subject.name}',
                    'user': {
                        'name': best_match.name,
                        'user_id': best_match.user_id,
                        'role': best_match.role,
                        'status': status,
                        'subject': active_subject.name
                    },
                    'timestamp': record.timestamp.strftime('%H:%M:%S'),
                    'distance': min_dist
                })
            else:
                msg = f'Face not recognized. (Score: {min_dist:.2f}, needs < {threshold})' if min_dist != float('inf') else 'Face not recognized.'
                return JsonResponse({'success': False, 'message': msg}, status=404)

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

# --- AUTH & DASHBOARD VIEWS ---

def login_view(request):
    if request.session.get('user_id'):
        return redirect('dashboard')
    return render(request, 'attendance/login.html')

def logout_view(request):
    request.session.flush()
    return redirect('index')

def dashboard_view(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    try:
        user = UserProfile.objects.get(user_id=user_id)
        
        # --- ANALYTICS LOGIC ---
        # 1. Total Attended (All successful attendance marks)
        attended_count = Attendance.objects.filter(user=user).count()

        # 2. Total Required (Count of ALL subject permissions for this semester)
        total_required = SubjectPermission.objects.filter(
            subject__semester=user.semester,
            subject__institute=user.institute
        ).count()
        
        # Calculate percentage (capped at 100% for safety)
        if total_required > 0:
            attendance_percentage = min(round((attended_count / total_required) * 100, 1), 100.0)
        else:
            # If no permissions exist but they have attendance, show 100%
            attendance_percentage = 100.0 if attended_count > 0 else 0.0

        # Get all subjects for this student's semester
        subjects_list = Subject.objects.filter(semester=user.semester, institute=user.institute)

        context = {
            'user': user,
            'total_class_days': total_required,
            'total_attended': attended_count,
            'attendance_percentage': attendance_percentage,
            'subjects': subjects_list
        }
        return render(request, 'attendance/dashboard.html', context)
    except UserProfile.DoesNotExist:
        request.session.flush()
        return redirect('login')

@csrf_exempt
def api_login(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            password = data.get('password')

            if not user_id or not password:
                return JsonResponse({'success': False, 'message': 'Provide ID and Password.'}, status=400)

            user = UserProfile.objects.get(user_id=user_id)
            
            if check_password(password, user.password):
                request.session['user_id'] = user.user_id
                return JsonResponse({'success': True, 'message': 'Login successful'})
            else:
                return JsonResponse({'success': False, 'message': 'Invalid password.'}, status=401)
                
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User ID not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_update_profile(request):
    if request.method == "POST":
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
            
        try:
            data = json.loads(request.body)
            user = UserProfile.objects.get(user_id=user_id)
            
            if user.role == 'student':
                # Students can only update their phone number
                if 'phone_number' in data: user.phone_number = data['phone_number']
            
            user.save()
            return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=405)

@csrf_exempt
def api_rescan_face(request):
    if request.method == "POST":
        user_id = request.session.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
            
        try:
            data = json.loads(request.body)
            descriptor = data.get('descriptor')
            if not descriptor or len(descriptor) != 128:
                return JsonResponse({'success': False, 'message': 'Invalid descriptor.'}, status=400)
                
            user = UserProfile.objects.get(user_id=user_id)
            user.face_encoding = json.dumps(descriptor)
            user.save()
            return JsonResponse({'success': True, 'message': 'Face data updated successfully'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=405)

# --- INSTITUTE VIEWS ---

def institute_register_view(request):
    return render(request, 'attendance/institute_register.html')

def institute_login_view(request):
    if request.session.get('institute_id'):
        return redirect('institute_dashboard')
    return render(request, 'attendance/institute_login.html')

def institute_logout_view(request):
    request.session.flush()
    return redirect('institute_login')

def institute_dashboard_view(request):
    institute_id = request.session.get('institute_id')
    if not institute_id:
        return redirect('institute_login')
    try:
        institute = Institute.objects.get(id=institute_id)
        members = institute.members.all().order_by('-created_at')
        return render(request, 'attendance/institute_dashboard.html', {'institute': institute, 'members': members})
    except Institute.DoesNotExist:
        request.session.flush()
        return redirect('institute_login')

@csrf_exempt
def api_institute_register(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get('name')
            password = data.get('password')
            contact_email = data.get('contact_email', '')
            contact_phone = data.get('contact_phone', '')
            address = data.get('address', '')
            
            if not name or not password:
                return JsonResponse({'success': False, 'message': 'Provide Name and Password.'}, status=400)

            institute = Institute.objects.create(
                name=name,
                password=make_password(password),
                contact_email=contact_email,
                contact_phone=contact_phone,
                address=address
            )
            return JsonResponse({
                'success': True,
                'message': 'Institute registered successfully!',
                'unique_code': institute.unique_code
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_institute_login(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            unique_code = data.get('unique_code')
            password = data.get('password')

            if not unique_code or not password:
                return JsonResponse({'success': False, 'message': 'Provide Unique Code and Password.'}, status=400)

            institute = Institute.objects.get(unique_code=unique_code)
            if check_password(password, institute.password):
                request.session['institute_id'] = institute.id
                return JsonResponse({'success': True, 'message': 'Login successful'})
            else:
                return JsonResponse({'success': False, 'message': 'Invalid password.'}, status=401)
        except Institute.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Institute not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_update_institute_details(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            institute = Institute.objects.get(id=institute_id)
            
            if 'lat' in data and data['lat'] is not None and data['lat'] != '':
                institute.latitude = float(data['lat'])
            if 'lon' in data and data['lon'] is not None and data['lon'] != '':
                institute.longitude = float(data['lon'])
                
            if 'contact_email' in data: institute.contact_email = data['contact_email']
            if 'contact_phone' in data: institute.contact_phone = data['contact_phone']
            if 'address' in data: institute.address = data['address']
            
            institute.save()
            return JsonResponse({'success': True, 'message': 'Institute details updated successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_institute_delete_user(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            if not user_id:
                return JsonResponse({'success': False, 'message': 'User ID required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            user_to_delete = UserProfile.objects.get(user_id=user_id, institute=institute)
            user_to_delete.delete()
            return JsonResponse({'success': True, 'message': 'User deleted successfully.'})
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found or does not belong to your institute.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_institute_edit_user(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            if not user_id:
                return JsonResponse({'success': False, 'message': 'User ID required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            user_to_edit = UserProfile.objects.get(user_id=user_id, institute=institute)
            
            if user_to_edit.role == 'student':
                if 'year' in data: user_to_edit.year = data['year']
                if 'semester' in data: user_to_edit.semester = data['semester']
                if 'department' in data: user_to_edit.department = data['department']
                if 'student_group' in data: user_to_edit.student_group = data['student_group']
                
            user_to_edit.save()
            return JsonResponse({'success': True, 'message': 'User updated successfully.'})
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found or does not belong to your institute.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

def institute_attendance_logs_view(request):
    institute_id = request.session.get('institute_id')
    if not institute_id:
        return redirect('institute_login')
    
    try:
        institute = Institute.objects.get(id=institute_id)
    except Institute.DoesNotExist:
        return redirect('institute_login')

    filter_type = request.GET.get('filter', 'all')
    attendances = Attendance.objects.filter(user__institute=institute)

    if filter_type == 'today':
        today = timezone.localtime(timezone.now()).date()
        attendances = attendances.filter(timestamp__date=today)
    elif filter_type == 'month':
        current_month = timezone.localtime(timezone.now()).month
        current_year = timezone.localtime(timezone.now()).year
        attendances = attendances.filter(timestamp__year=current_year, timestamp__month=current_month)

    attendances = attendances.order_by('-timestamp')

    context = {
        'institute': institute,
        'attendances': attendances,
        'filter_type': filter_type
    }
    return render(request, 'attendance/institute_attendance_logs.html', context)

@csrf_exempt
def api_institute_delete_attendance(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            attendance_id = data.get('attendance_id')
            if not attendance_id:
                return JsonResponse({'success': False, 'message': 'Attendance ID required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            # Ensure the attendance record belongs to a user registered at this institute
            attendance_record = Attendance.objects.get(id=attendance_id, user__institute=institute)
            attendance_record.delete()
            return JsonResponse({'success': True, 'message': 'Attendance record deleted successfully.'})
        except Attendance.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Record not found or unauthorized.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_institute_delete(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            password = data.get('password')
            if not password:
                return JsonResponse({'success': False, 'message': 'Password is required to delete the account.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            if check_password(password, institute.password):
                institute.delete()
                request.session.flush()
                return JsonResponse({'success': True, 'message': 'Institute deleted successfully.'})
            else:
                return JsonResponse({'success': False, 'message': 'Incorrect password.'}, status=401)
        except Institute.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Institute not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

def institute_subjects_view(request):
    institute_id = request.session.get('institute_id')
    if not institute_id:
        return redirect('institute_login')
    
    try:
        institute = Institute.objects.get(id=institute_id)
        # Group subjects by semester
        subjects = institute.subjects.all().order_by('semester', 'name')
        
        # Get semester choices from UserProfile
        semester_choices = UserProfile.SEMESTER_CHOICES
        
        return render(request, 'attendance/institute_subjects.html', {
            'institute': institute,
            'subjects': subjects,
            'semester_choices': semester_choices
        })
    except Institute.DoesNotExist:
        request.session.flush()
        return redirect('institute_login')

@csrf_exempt
def api_institute_add_subject(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            semester = data.get('semester')
            name = data.get('name')
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            
            if not semester or not name or not start_time or not end_time:
                return JsonResponse({'success': False, 'message': 'Semester, Subject Name, Start Time, and End Time are required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            subject = Subject.objects.create(
                institute=institute,
                semester=semester,
                name=name,
                start_time=start_time,
                end_time=end_time
            )
            return JsonResponse({
                'success': True, 
                'message': 'Subject added successfully!',
                'subject': {
                    'id': subject.id,
                    'name': subject.name,
                    'semester': subject.semester,
                    'start_time': str(subject.start_time),
                    'end_time': str(subject.end_time)
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

def institute_daily_schedule_view(request):
    institute_id = request.session.get('institute_id')
    if not institute_id:
        return redirect('institute_login')
    
    try:
        institute = Institute.objects.get(id=institute_id)
        today = timezone.localtime().date()
        
        subjects = institute.subjects.all().order_by('semester', 'start_time')
        # Get which subjects have permission for today
        permitted_ids = SubjectPermission.objects.filter(date=today, subject__institute=institute).values_list('subject_id', flat=True)
        
        now = timezone.localtime()
        current_time = now.time()
        
        return render(request, 'attendance/institute_daily_schedule.html', {
            'institute': institute,
            'subjects': subjects,
            'permitted_ids': list(permitted_ids),
            'today': today,
            'current_time': current_time,
            'semester_choices': UserProfile.SEMESTER_CHOICES
        })
    except Institute.DoesNotExist:
        request.session.flush()
        return redirect('institute_login')

@csrf_exempt
def api_institute_toggle_permission(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            subject_id = data.get('subject_id')
            active = data.get('active') # Boolean
            
            if not subject_id:
                return JsonResponse({'success': False, 'message': 'Subject ID required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            subject = Subject.objects.get(id=subject_id, institute=institute)
            today = timezone.localtime().date()
            
            if active:
                SubjectPermission.objects.get_or_create(subject=subject, date=today)
                message = "Permission granted for today."
            else:
                SubjectPermission.objects.filter(subject=subject, date=today).delete()
                message = "Permission revoked for today."
                
            return JsonResponse({'success': True, 'message': message})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_institute_delete_subject(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            subject_id = data.get('subject_id')
            if not subject_id:
                return JsonResponse({'success': False, 'message': 'Subject ID required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            subject = Subject.objects.get(id=subject_id, institute=institute)
            subject.delete()
            return JsonResponse({'success': True, 'message': 'Subject deleted successfully.'})
        except Subject.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Subject not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method.'}, status=405)

@csrf_exempt
def api_student_day_details(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        date_str = data.get('date') # Format: YYYY-MM-DD
        if not date_str:
            return JsonResponse({'success': False, 'message': 'Date required'}, status=400)
        
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        user = UserProfile.objects.get(user_id=user_id)
        
        # Get all permissions for this student's semester on this date
        permissions = SubjectPermission.objects.filter(
            date=target_date,
            subject__semester=user.semester,
            subject__institute=user.institute
        ).select_related('subject')
        
        # Get all attendance records for this student on this date
        day_start = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.min))
        day_end = timezone.make_aware(datetime.datetime.combine(target_date, datetime.time.max))
        
        attendances = Attendance.objects.filter(
            user=user,
            timestamp__range=(day_start, day_end)
        )
        
        results = []
        for perm in permissions:
            subj = perm.subject
            # Check if attended this specific subject
            att = attendances.filter(subject=subj).first()
            
            results.append({
                'subject_name': subj.name,
                'start_time': subj.start_time.strftime('%H:%M') if subj.start_time else 'N/A',
                'end_time': subj.end_time.strftime('%H:%M') if subj.end_time else 'N/A',
                'attended': att is not None,
                'status': att.status if att else 'Absent',
                'time': att.timestamp.strftime('%H:%M') if att else None
            })
            
        return JsonResponse({'success': True, 'subjects': results})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@csrf_exempt
def api_institute_rescan_student_face(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            descriptor = data.get('descriptor')
            inst_pass = data.get('institute_password')
            stud_pass = data.get('student_password')
            
            if not all([student_id, descriptor, inst_pass, stud_pass]):
                return JsonResponse({'success': False, 'message': 'Missing required fields.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            # Verify Institute Password
            if not check_password(inst_pass, institute.password):
                return JsonResponse({'success': False, 'message': 'Incorrect institute password.'}, status=403)
            
            # Verify Student exists and belongs to this institute
            student = UserProfile.objects.get(user_id=student_id, institute=institute)
            # Verify Student Password
            if not check_password(stud_pass, student.password):
                return JsonResponse({'success': False, 'message': 'Incorrect student password.'}, status=403)
            
            # Update Face Encoding
            student.face_encoding = json.dumps(descriptor)
            student.save()
            
            return JsonResponse({'success': True, 'message': 'Student face data updated successfully.'})
            
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Student not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False}, status=405)
