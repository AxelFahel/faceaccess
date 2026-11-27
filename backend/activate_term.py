import sqlite3
import hashlib
import secrets

conn = sqlite3.connect("C:/Users/Aksel/faceaccess/backend/faceaccess.db")
c = conn.cursor()
c.execute("SELECT id, code, name FROM terminals WHERE code = 'TERM-PORTARIA'")
row = c.fetchone()
print("Found terminal:", row)

secret = secrets.token_hex(32)
s_hash = hashlib.sha256(secret.encode()).hexdigest()
prefix = secret[:8]

c.execute("""
    UPDATE terminals
    SET status = 'active',
        credential_prefix = ?,
        credential_hash = ?,
        credential_issued_at = datetime('now')
    WHERE code = 'TERM-PORTARIA'
""", (prefix, s_hash))
conn.commit()

# Also let's ensure TERM-01 is active so demo/fallback works too
c.execute("SELECT id FROM terminals WHERE code = 'TERM-01'")
term01 = c.fetchone()
demo_secret = "demo-secret"
demo_hash = hashlib.sha256(demo_secret.encode()).hexdigest()
if term01:
    c.execute("""
        UPDATE terminals
        SET status = 'active',
            credential_prefix = 'demo-sec',
            credential_hash = ?,
            credential_issued_at = datetime('now')
        WHERE code = 'TERM-01'
    """, (demo_hash,))
    conn.commit()
    print("TERM-01 updated with demo-secret.")

print("ACTIVATION COMPLETE!")
print(f"TERMINAL_CODE=TERM-PORTARIA")
print(f"TERMINAL_SECRET={secret}")
