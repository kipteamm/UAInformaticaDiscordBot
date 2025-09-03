import sqlite3
import random
import string
import time


conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()


c.execute('''
CREATE TABLE IF NOT EXISTS verifications (
    discord_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_attempt FLOAT DEFAULT NULL,
    email_timestamp FLOAT NOT NULL
)
''')
conn.commit()


def _generate_code() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))


def create_entry(discord_id: int, email: str) -> str:
    code = _generate_code()

    c.execute('INSERT OR REPLACE INTO verifications (discord_id, email, code, verified, email_timestamp) VALUES (?, ?, ?, 0, ?)', (discord_id, email, code, time.time()))
    conn.commit()

    return code


def verify_code(discord_id: int, code: str) -> tuple[bool, str]:
    c.execute("SELECT * FROM verifications WHERE discord_id = ?", (discord_id,))
    result = c.fetchone()

    if not result:
        return False, "❌ Er is nog geen email naar je verstuurd."
    
    if result[3]:
        return False, "✅ U bent al geverifieerd."

    if result[2] == code:
        c.execute("UPDATE verifications SET verified = 1 WHERE discord_id = ?", (discord_id,))
        conn.commit()
        return True, "✅ U bent nu geverifieerd."
    
    if result[5]:
        time_passed = time.time() - result[5]
        if time_passed >= 86400:
            result[4] = 0
            c.execute("UPDATE verifications SET verified = 1 WHERE discord_id = ?", (discord_id,))
            conn.commit()

        if result[4] == 5:
            return False, f"❌ Maximum aantal pogingen overschreden, u zult {24 - round(time_passed / 3600)}u moeten wachten."

    c.execute("UPDATE verifications SET attempts = ?, last_attempt = ? WHERE discord_id = ?", (result[4] + 1, time.time(), discord_id))
    conn.commit()    
    return False, "❌ Code is niet correct."


def email_exists(email: str) -> bool:
    c.execute("SELECT 1 FROM verifications WHERE email = ?", (email,))
    return c.fetchone() != None


def is_verified(discord_id: int) -> bool:
    c.execute("SELECT 1 FROM verifications WHERE discord_id = ? AND verified = 1", (discord_id,))
    return c.fetchone() != None


def is_pending(discord_id: int) -> bool:
    c.execute("SELECT 1 FROM verifications WHERE discord_id = ?", (discord_id,))
    return c.fetchone() != None


def can_retry(discord_id: int) -> tuple[bool, str]:
    c.execute("SELECT * FROM verifications WHERE discord_id = ?", (discord_id,))
    result = c.fetchone()
    if not result:
        return False, "❌ U moet nog op de 'Voer e-mailadres in' knop drukken."
    
    time_passed = time.time() - result[6]
    if time_passed < 300:
        return False, "❌ Er zijn nog geen 5 minuten gepasseerd."
    
    c.execute("UPDATE verifications SET email_timestamp = ? WHERE discord_id = ?", (time.time(), discord_id))
    conn.commit()
    
    return True, "✅ Een nieuwe verificatie email werd verstuurd."


def remove_entry(discord_id: int) -> None:
    c.execute("DELETE FROM verifications WHERE discord_id = ?", (discord_id,))
    conn.commit()


def get_email(discord_id: int) -> tuple | None:
    c.execute("SELECT email, attempts, email_timestamp FROM verifications WHERE discord_id = ?", (discord_id, ))
    return c.fetchone()
