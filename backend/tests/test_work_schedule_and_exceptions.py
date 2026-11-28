import json
import uuid
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = 'http://127.0.0.1:8000'
RUN_ID = uuid.uuid4().hex[:6].upper()

# 1. Login as admin
login_res = requests.post(
    f'{BASE_URL}/api/v1/auth/login',
    json={'email': 'admin@faceaccess.com', 'password': 'Admin@Secure2026!'}
)
assert login_res.status_code == 200, f'Admin login failed: {login_res.text}'
admin_token = login_res.json()['access_token']
headers_admin = {'Authorization': f'Bearer {admin_token}'}

# Get unit
units = requests.get(f'{BASE_URL}/api/v1/organization/units', headers=headers_admin).json()
unit_id = units[0]['id']

# Terminal headers
term_secret = '55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d'
headers_term = {'X-Terminal-Code': 'TERM-PORTARIA', 'X-Terminal-Secret': term_secret}

print('=== Test 1: Employee with schedule outside working hours (Rejection) ===')
# Create a strict work schedule that is NOT today or has different hours
# Current UTC/Local time
now = datetime.now(timezone.utc)
# Let's create a schedule where today is a day off (only Sunday or a specific day)
# If today is weekday W, set schedule to (W + 1) % 7
today_weekday = datetime.now().weekday()
other_weekday = (today_weekday + 1) % 7

sched_res = requests.post(f'{BASE_URL}/api/v1/schedules', headers=headers_admin, json={
    'name': 'Jornada Outro Dia',
    'description': 'Escala que nao inclui o dia de hoje',
    'tolerance_minutes': 10,
    'days': [{'weekday': other_weekday, 'start': '08:00', 'end': '17:00', 'break_minutes': 60}]
})
assert sched_res.status_code == 200, sched_res.text
sched_id = sched_res.json()['id']

# Create employee assigned to this schedule
out_mat = f'MAT-OUT-{RUN_ID}'
emp_res = requests.post(f'{BASE_URL}/api/v1/employees', headers=headers_admin, json={
    'full_name': 'Funcionario Fora de Horario',
    'registration_number': out_mat,
    'email': f'fora.{RUN_ID}@empresa.com',
    'unit_id': unit_id,
    'work_schedule_id': sched_id,
    'pin': '9999'
})
assert emp_res.status_code == 200, emp_res.text
emp_id = emp_res.json()['id']

# Attempt totem verification outside work hours (No exception registered)
kiosk_res = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': out_mat,
    'method': 'pin',
    'pin': '9999',
    'operation_type': 'attendance'
})
print('Kiosk Response (Outside Hours, No Exception):', kiosk_res.json())
assert kiosk_res.json()['status'] == 'rejected', 'Expected rejection outside hours'
assert kiosk_res.json()['access_decision'] == 'denied'
assert 'fora do horário de trabalho' in kiosk_res.json()['message'].lower() or 'folga' in kiosk_res.json()['message'].lower()
print('PASS: Access rejected when outside scheduled working hours!')

print('\n=== Test 2: Register Schedule Exception (Access Granted!) ===')
# Register exception covering right now
exc_res = requests.post(f'{BASE_URL}/api/v1/schedules/exceptions', headers=headers_admin, json={
    'employee_id': emp_id,
    'starts_at': (now - timedelta(minutes=10)).isoformat(),
    'ends_at': (now + timedelta(hours=3)).isoformat(),
    'reason': 'Hora extra autorizada para fechamento de balanço',
    'exception_type': 'overtime'
})
assert exc_res.status_code == 200, exc_res.text
exc_id = exc_res.json()['id']
print('Exception created:', exc_res.json())

# Attempt totem verification with active registered exception
kiosk_exc = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': out_mat,
    'method': 'pin',
    'pin': '9999',
    'operation_type': 'attendance'
})
print('Kiosk Response with Exception:', kiosk_exc.json())
assert kiosk_exc.json()['status'] == 'verified', 'Expected access granted by exception'
assert kiosk_exc.json()['access_decision'] == 'granted'
assert 'EXCEÇÃO REGISTRADA' in kiosk_exc.json()['message']
assert 'Hora extra autorizada' in kiosk_exc.json()['message']
print('PASS: Access granted by registered exception!')

# Verify that the exception usage was tracked in DB
exc_check = requests.get(f'{BASE_URL}/api/v1/schedules/exceptions?employee_id={emp_id}', headers=headers_admin).json()
assert len(exc_check) > 0
assert exc_check[0]['access_count'] >= 1
assert exc_check[0]['used_at'] is not None
print('PASS: Exception usage tracked (used_at and access_count)!')

print('\n=== Test 3: Cancel Exception (Immediate Rejection Reinstated) ===')
cancel_res = requests.post(f'{BASE_URL}/api/v1/schedules/exceptions/{exc_id}/cancel', headers=headers_admin, json={
    'cancel_reason': 'Serviço encerrado antecipadamente'
})
assert cancel_res.status_code == 200, cancel_res.text

# Totem verify again: must be rejected now that exception was cancelled
kiosk_cancelled = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': out_mat,
    'method': 'pin',
    'pin': '9999',
    'operation_type': 'attendance'
})
print('Kiosk Response after Cancelled Exception:', kiosk_cancelled.json())
assert kiosk_cancelled.json()['status'] == 'rejected'
assert kiosk_cancelled.json()['access_decision'] == 'denied'
print('PASS: Access promptly revoked after exception is cancelled!')

print('\n=== Test 4: Employee within active regular work hours ===')
# Create schedule where today is working and current time is within window (00:00 - 23:59)
start_time = '00:00'
end_time = '23:59'

sched_active = requests.post(f'{BASE_URL}/api/v1/schedules', headers=headers_admin, json={
    'name': 'Jornada Vigente Agora',
    'tolerance_minutes': 15,
    'days': [{'weekday': today_weekday, 'start': start_time, 'end': end_time, 'break_minutes': 60}]
}).json()

in_mat = f'MAT-IN-{RUN_ID}'
emp_active = requests.post(f'{BASE_URL}/api/v1/employees', headers=headers_admin, json={
    'full_name': 'Funcionario Em Horario Normal',
    'registration_number': in_mat,
    'email': f'em.{RUN_ID}@empresa.com',
    'unit_id': unit_id,
    'work_schedule_id': sched_active['id'],
    'pin': '8888'
}).json()

kiosk_active = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': in_mat,
    'method': 'pin',
    'pin': '8888',
    'operation_type': 'attendance'
})
print('Kiosk Response during Normal Hours:', kiosk_active.json())
assert kiosk_active.json()['status'] == 'verified'
assert kiosk_active.json()['access_decision'] == 'granted'
print('PASS: Normal scheduled hours granted access without needing exception!')

print('\n>>> ALL 4 WORK SCHEDULE & EXCEPTION TESTS PASSED! <<<')
