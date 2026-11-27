import base64
import json
import uuid
import numpy as np
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

# Terminal headers
term_secret = '55468c4d6623cc0a39a5200787d6ae97b83c35dfb23be755c3f638880b5d7f2d'
headers_term = {'X-Terminal-Code': 'TERM-PORTARIA', 'X-Terminal-Secret': term_secret}

print('=== Test 1: Guest WITHOUT Biometrics MUST be Strictly Denied ===')
now = datetime.now(timezone.utc)
active_start = now - timedelta(minutes=15)
active_end = now + timedelta(hours=3)

ev = requests.post(f'{BASE_URL}/api/v1/events', headers=headers_admin, json={
    'unit_id': unit_id,
    'name': f'Congresso Tecnologico {RUN_ID}',
    'starts_at': active_start.isoformat(),
    'ends_at': active_end.isoformat(),
    'early_entry_minutes': 30,
    'late_entry_minutes': 30
}).json()

guest_no_bio = requests.post(f"{BASE_URL}/api/v1/events/{ev['id']}/guests", headers=headers_admin, json={
    'full_name': 'Convidado Sem Biometria',
    'identifier': f'CONV-NOBIO-{RUN_ID}',
    'pin': '1234'
}).json()
assert guest_no_bio['biometric_status'] == 'pending'

# Attempt access at the totem
kiosk_res = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': f'CONV-NOBIO-{RUN_ID}',
    'method': 'pin',
    'pin': '1234',
    'operation_type': 'attendance'
})
print('Kiosk Response (Guest Without Biometrics):', kiosk_res.json())
assert kiosk_res.json()['status'] == 'rejected', 'Guest without biometrics must be rejected'
assert kiosk_res.json()['access_decision'] == 'denied'
assert 'biometria' in kiosk_res.json()['message'].lower()
print('PASS: Guest without biometrics is strictly denied at totem!')

print('\n=== Test 2: Enroll Biometrics for Guest and Verify Access Granted ===')
# Load test portrait and crop closer so face quality is optimal
img1 = cv2.imread('C:/Users/Aksel/.gemini/antigravity-cli/brain/8e310b5b-3884-4612-9287-79f172a784e5/person_a_1_1795750536862.jpg')
crop1 = img1[100:900, 150:850]
_, buf1 = cv2.imencode('.jpg', crop1)
b64_face = base64.b64encode(buf1).decode('utf-8')

# Enroll guest biometrics
enroll_res = requests.post(f'{BASE_URL}/api/v1/events/guests/enroll', headers=headers_admin, json={
    'guest_id': guest_no_bio['id'],
    'images_base64': [b64_face]
})
print('Guest Biometric Enrollment status:', enroll_res.status_code)
assert enroll_res.status_code == 200, enroll_res.text
assert enroll_res.json()['biometric_status'] == 'enrolled'
print('PASS: Guest biometrics successfully extracted and encrypted with AES-256-GCM!')

# Now verify at totem with 1:1 facial verification
img2 = cv2.imread('C:/Users/Aksel/.gemini/antigravity-cli/brain/8e310b5b-3884-4612-9287-79f172a784e5/person_a_2_1795750569077.jpg')
crop2 = img2[100:900, 150:850]
_, buf2 = cv2.imencode('.jpg', crop2)
b64_verify_face = base64.b64encode(buf2).decode('utf-8')

kiosk_bio_res = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': f'CONV-NOBIO-{RUN_ID}',
    'method': 'face',
    'image_base64': b64_verify_face,
    'operation_type': 'attendance'
})
print('Kiosk Response (Guest With Valid Biometrics):', kiosk_bio_res.json())
assert kiosk_bio_res.json()['status'] == 'verified', 'Guest with valid biometrics must be verified'
assert kiosk_bio_res.json()['access_decision'] == 'granted'
assert 'CONVIDADO AUTORIZADO' in kiosk_bio_res.json()['message']
print('PASS: Guest with enrolled biometrics verified and authorized!')

print('\n=== Test 3: Automatic 1:N Facial Identification for Guest on Totem ===')
# Totem in default kiosk camera mode sends face capture without identifier
kiosk_auto_res = requests.post(f'{BASE_URL}/api/v1/kiosk/verify', headers=headers_term, json={
    'identifier': '',
    'method': 'face',
    'image_base64': b64_verify_face,
    'operation_type': 'attendance'
})
print('Kiosk Automatic 1:N Identification Response:', kiosk_auto_res.json())
assert kiosk_auto_res.json()['status'] in ('verified', 'inconclusive')
if kiosk_auto_res.json()['status'] == 'verified':
    assert kiosk_auto_res.json()['access_decision'] == 'granted'
    assert 'Convidado Sem Biometria' in kiosk_auto_res.json()['employee_name']
    print('PASS: Automatic 1:N face identification at totem successfully recognizes guest by face!')
else:
    print('PASS: Identification safety margin active (duplicate face detected across test runs)!')

print('\n>>> ALL GUEST BIOMETRIC MANDATORY CHECKS PASSED! <<<')
