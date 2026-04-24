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
from .models import UserProfile, Attendance, Institute

# Dummy configurations (can be moved to settings.py)
MAX_DISTANCE_METERS = 100 # Maximum distance in meters to allow attendance
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
            grade_class = data.get('grade_class', '')
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

            # Generate secure random password
            raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            user_profile = UserProfile.objects.create(
                name=name,
                role=role,
                institute=institute,
                department=department,
                grade_class=grade_class,
                roll_number=roll_number,
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

            if best_match and min_dist < threshold:
                if not best_match.institute:
                    return JsonResponse({'success': False, 'message': 'User is not linked to any institute.'}, status=400)
                    
                dist_to_school = haversine(float(lat), float(lon), best_match.institute.latitude, best_match.institute.longitude)
                if dist_to_school > MAX_DISTANCE_METERS:
                    return JsonResponse({'success': False, 'message': f'You are too far from your institute. ({int(dist_to_school)}m away)'}, status=400)

                # Check for double attendance safely using exact bounds (fixing SQLite __date bugs)
                now = timezone.localtime()
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + datetime.timedelta(days=1)
                
                if Attendance.objects.filter(user=best_match, timestamp__gte=today_start, timestamp__lt=today_end).exists():
                    return JsonResponse({'success': False, 'message': 'Attendance already marked for today.'}, status=400)
                
                # Check late entry
                current_time = timezone.localtime().time()
                status = 'Late' if current_time > LATE_CUTOFF_TIME else 'Present'
                
                # Mark attendance
                record = Attendance.objects.create(user=best_match, status=status)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Attendance marked: {status} for {best_match.name}',
                    'user': {
                        'name': best_match.name,
                        'user_id': best_match.user_id,
                        'role': best_match.role,
                        'status': status
                    },
                    'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
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
        
        # Calculate attendance statistics
        # Total days the system recorded *any* attendance (proxy for total class days)
        total_class_days = Attendance.objects.dates('timestamp', 'day').count()
        # Total days this user was present
        total_attended = Attendance.objects.filter(user=user).count()
        
        attendance_percentage = 0
        if total_class_days > 0:
            attendance_percentage = int((total_attended / total_class_days) * 100)
            if attendance_percentage > 100:
                attendance_percentage = 100

        context = {
            'user': user,
            'total_class_days': total_class_days,
            'total_attended': total_attended,
            'attendance_percentage': attendance_percentage
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
            
            if 'name' in data: user.name = data['name']
            if 'department' in data: user.department = data['department']
            if 'grade_class' in data: user.grade_class = data['grade_class']
            if 'roll_number' in data: user.roll_number = data['roll_number']
            
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
            if not name or not password:
                return JsonResponse({'success': False, 'message': 'Provide Name and Password.'}, status=400)

            institute = Institute.objects.create(
                name=name,
                password=make_password(password)
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
def api_update_institute_location(request):
    if request.method == "POST":
        institute_id = request.session.get('institute_id')
        if not institute_id:
            return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            if lat is None or lon is None:
                return JsonResponse({'success': False, 'message': 'Latitude and longitude are required.'}, status=400)
            
            institute = Institute.objects.get(id=institute_id)
            institute.latitude = float(lat)
            institute.longitude = float(lon)
            institute.save()
            return JsonResponse({'success': True, 'message': 'Location updated successfully.'})
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
