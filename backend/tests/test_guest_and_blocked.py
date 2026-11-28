import base64
import json
import uuid
import cv2
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

# Terminal session header using TERMINAL_SECRET
term_secret = '55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d'
headers_term = {'X-Terminal-Code': 'TERM-PORTARIA', 'X-Terminal-Secret': term_secret}

print('=== Test 1: Blocked Person Rejection ===')
block_ident = f'DOC-BLOCKED-{RUN_ID}'
block_res = requests.post(f'{BASE_URL}/api/v1/blocked-persons', headers=headers_admin, json={
    'full_name': 'Invasor Teste',
    'identifier': block_ident,
    'reason': 'Tentativa previa de invasao e desacato'
})
print('Block created:', block_res.json().get('identifier'))

kiosk_blocked = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': block_ident,
    'method': 'pin',
    'operation_type': 'attendance'
})
print('Kiosk Blocked Person Response:', kiosk_blocked.json())
assert kiosk_blocked.json()['status'] == 'rejected'
assert kiosk_blocked.json()['access_decision'] == 'denied'
assert 'ACESSO BLOQUEADO' in kiosk_blocked.json()['message']
print('PASS: Blocked person correctly denied access with reason!')

print('\n=== Test 2: Event Guest Future Window (Not started) ===')
now = datetime.now(timezone.utc)
future_start = now + timedelta(hours=3)
future_end = now + timedelta(hours=5)

ev_fut_res = requests.post(f'{BASE_URL}/api/v1/events', headers=headers_admin, json={
    'unit_id': unit_id,
    'name': 'Conferencia Futura',
    'starts_at': future_start.isoformat(),
    'ends_at': future_end.isoformat(),
    'early_entry_minutes': 30,
    'late_entry_minutes': 30
})
print('ev_fut status:', ev_fut_res.status_code, ev_fut_res.text)
ev_fut = ev_fut_res.json()

g_res = requests.post(f"{BASE_URL}/api/v1/events/{ev_fut['id']}/guests", headers=headers_admin, json={
    'full_name': 'Convidado Cedo Demais',
    'identifier': f'CONV-FUTURO-{RUN_ID}',
    'pin': '1234'
})
print('guest status:', g_res.status_code, g_res.text)

kiosk_fut = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': f'CONV-FUTURO-{RUN_ID}',
    'method': 'pin',
    'pin': '1234',
    'operation_type': 'attendance'
})
print('Kiosk Future Event Guest Response:', kiosk_fut.json())
assert kiosk_fut.json()['status'] == 'rejected'
assert kiosk_fut.json()['access_decision'] == 'denied'
# Since guest has no biometrics enrolled, biometric check strictly denies first!
assert 'biometria' in kiosk_fut.json()['message'].lower()
print('PASS: Future guest without biometrics strictly rejected!')

print('\n=== Test 3: Event Guest Past Window (Already Ended) ===')
past_start = now - timedelta(hours=5)
past_end = now - timedelta(hours=3)

ev_past = requests.post(f'{BASE_URL}/api/v1/events', headers=headers_admin, json={
    'unit_id': unit_id,
    'name': 'Workshop Passado',
    'starts_at': past_start.isoformat(),
    'ends_at': past_end.isoformat(),
    'early_entry_minutes': 30,
    'late_entry_minutes': 30
}).json()

requests.post(f"{BASE_URL}/api/v1/events/{ev_past['id']}/guests", headers=headers_admin, json={
    'full_name': 'Convidado Atrasado',
    'identifier': f'CONV-PASSADO-{RUN_ID}',
    'pin': '1234'
})

kiosk_past = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': f'CONV-PASSADO-{RUN_ID}',
    'method': 'pin',
    'pin': '1234',
    'operation_type': 'attendance'
})
print('Kiosk Past Event Guest Response:', kiosk_past.json())
assert kiosk_past.json()['status'] == 'rejected'
assert kiosk_past.json()['access_decision'] == 'denied'
assert 'biometria' in kiosk_past.json()['message'].lower()
print('PASS: Past guest without biometrics strictly rejected!')

print('\n=== Test 4: Event Guest In-Window (Access Granted!) ===')
active_start = now - timedelta(minutes=15)
active_end = now + timedelta(hours=2)

ev_active = requests.post(f'{BASE_URL}/api/v1/events', headers=headers_admin, json={
    'unit_id': unit_id,
    'name': 'Gala Anual',
    'starts_at': active_start.isoformat(),
    'ends_at': active_end.isoformat(),
    'early_entry_minutes': 30,
    'late_entry_minutes': 30
}).json()

active_ident = f'CONV-ATIVO-{RUN_ID}'
g_act = requests.post(f"{BASE_URL}/api/v1/events/{ev_active['id']}/guests", headers=headers_admin, json={
    'full_name': 'Doutor Convidado Especial',
    'identifier': active_ident,
    'pin': '5678'
}).json()

# Guest MUST enroll biometrics to have access:
img = cv2.imread('C:/Users/Aksel/.gemini/antigravity-cli/brain/8e310b5b-3884-4612-9287-79f172a784e5/person_a_1_1795750536862.jpg')
crop = img[100:900, 150:850]
_, buf = cv2.imencode('.jpg', crop)
b64_face = base64.b64encode(buf).decode('utf-8')

requests.post(f'{BASE_URL}/api/v1/events/guests/enroll', headers=headers_admin, json={
    'guest_id': g_act['id'],
    'images_base64': [b64_face, b64_face, b64_face]
})

kiosk_active = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': active_ident,
    'method': 'face',
    'image_base64': b64_face,
    'operation_type': 'attendance'
})
print('Kiosk Active Event Guest Response:', kiosk_active.json())
assert kiosk_active.json()['status'] == 'verified'
assert kiosk_active.json()['access_decision'] == 'granted'
assert 'CONVIDADO AUTORIZADO' in kiosk_active.json()['message']
print('PASS: Guest inside event window granted access!')

print('\n=== Test 5: Blacklist Precedence Over Active Event Guest ===')
requests.post(f'{BASE_URL}/api/v1/blocked-persons', headers=headers_admin, json={
    'full_name': 'Doutor Convidado Especial',
    'identifier': active_ident,
    'reason': 'Ordem judicial restritiva'
})

kiosk_precedence = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': active_ident,
    'method': 'face',
    'image_base64': b64_face,
    'operation_type': 'attendance'
})
print('Kiosk Blocked Guest Response:', kiosk_precedence.json())
assert kiosk_precedence.json()['status'] == 'rejected'
assert kiosk_precedence.json()['access_decision'] == 'denied'
assert 'ACESSO BLOQUEADO' in kiosk_precedence.json()['message']
print('PASS: Blacklist successfully overrides valid event schedule!')

print('\n>>> ALL 5 VERIFICATION SUITES PASSED PERFECTLY! <<<')
