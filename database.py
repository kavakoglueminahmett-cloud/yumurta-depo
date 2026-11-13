"""
Yumurta Depo Yönetim Sistemi - Veritabanı Modülü
SQLite veritabanı oluşturma, başlatma ve yardımcı fonksiyonlar.
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yumurta_depo.db")

# Python 3.9 uyumluluğu için pbkdf2 kullanıyoruz
def _hash_pw(password):
    return generate_password_hash(password, method="pbkdf2:sha256")


def get_db():
    """Veritabanı bağlantısı döndürür."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Veritabanını oluşturur ve varsayılan verileri ekler."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            password    TEXT    NOT NULL,
            full_name   TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS egg_types (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    UNIQUE NOT NULL,
            initial_stock INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS buyers (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id             INTEGER   PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER   NOT NULL,
            egg_type_id    INTEGER   NOT NULL,
            supplier_id    INTEGER   NOT NULL,
            quantity       INTEGER   NOT NULL,
            unit_price     REAL      NOT NULL,
            total_price    REAL      NOT NULL,
            paid_amount    REAL      NOT NULL DEFAULT 0,
            payment_method TEXT      NOT NULL DEFAULT 'Nakit',
            date           TEXT      NOT NULL,
            note           TEXT      DEFAULT '',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)     REFERENCES users(id),
            FOREIGN KEY (egg_type_id) REFERENCES egg_types(id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id             INTEGER   PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER   NOT NULL,
            egg_type_id    INTEGER   NOT NULL,
            buyer_id       INTEGER   NOT NULL,
            quantity       INTEGER   NOT NULL,
            unit_price     REAL      NOT NULL,
            total_price    REAL      NOT NULL,
            paid_amount    REAL      NOT NULL DEFAULT 0,
            payment_method TEXT      NOT NULL DEFAULT 'Nakit',
            date           TEXT      NOT NULL,
            note           TEXT      DEFAULT '',
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)     REFERENCES users(id),
            FOREIGN KEY (egg_type_id) REFERENCES egg_types(id),
            FOREIGN KEY (buyer_id)    REFERENCES buyers(id)
        );
    """)

    # -- Migration: paid_amount ve payment_method sütunlarını kontrol et --
    purchases_cols = [c[1] for c in cursor.execute("PRAGMA table_info(purchases)").fetchall()]
    if "paid_amount" not in purchases_cols:
        cursor.execute("ALTER TABLE purchases ADD COLUMN paid_amount REAL NOT NULL DEFAULT 0")
        cursor.execute("UPDATE purchases SET paid_amount = total_price")
    if "payment_method" not in purchases_cols:
        cursor.execute("ALTER TABLE purchases ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'Nakit'")
        cursor.execute("UPDATE purchases SET payment_method = 'Nakit'")

    sales_cols = [c[1] for c in cursor.execute("PRAGMA table_info(sales)").fetchall()]
    if "paid_amount" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN paid_amount REAL NOT NULL DEFAULT 0")
        cursor.execute("UPDATE sales SET paid_amount = total_price")
    if "payment_method" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'Nakit'")
        cursor.execute("UPDATE sales SET payment_method = 'Nakit'")

    # -- Varsayılan kullanıcılar --
    if cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            [
                ("ahmet",  _hash_pw("ahmet123"),  "Ahmet"),
                ("mehmet", _hash_pw("mehmet123"), "Mehmet"),
                ("ali",    _hash_pw("ali123"),    "Ali"),
            ],
        )

    # -- Varsayılan yumurta çeşitleri --
    if cursor.execute("SELECT COUNT(*) FROM egg_types").fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO egg_types (name, initial_stock) VALUES (?, ?)",
            [
                ("Beyaz Yumurta", 1000),
                ("Kırmızı Yumurta", 1000),
                ("Organik Yumurta", 500),
                ("Köy Yumurtası", 500),
                ("Gezen Tavuk Yumurtası", 500),
            ],
        )

    # -- Varsayılan tedarikçi firmalar --
    if cursor.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO suppliers (name) VALUES (?)",
            [
                ("Anadolu Çiftliği A.Ş.",),
                ("Bereket Yumurta Üretim",),
                ("Doğal Yaşam Tavukçuluk",),
            ],
        )

    # -- Varsayılan alıcı / müşteri firmalar --
    if cursor.execute("SELECT COUNT(*) FROM buyers").fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO buyers (name) VALUES (?)",
            [
                ("Yıldız Marketler",),
                ("Merkez Pastaneleri",),
                ("Güneş Gıda Toptan",),
            ],
        )

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════
#  STOK
# ═══════════════════════════════════════════════════════════

def get_stock():
    """Her yumurta çeşidi için güncel stok miktarını döndürür (adet)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            et.id,
            et.name,
            et.initial_stock,
            COALESCE(p.total_in, 0)  AS total_in,
            COALESCE(s.total_out, 0) AS total_out,
            et.initial_stock + COALESCE(p.total_in, 0) - COALESCE(s.total_out, 0) AS stock
        FROM egg_types et
        LEFT JOIN (
            SELECT egg_type_id, SUM(quantity) AS total_in
            FROM purchases GROUP BY egg_type_id
        ) p ON p.egg_type_id = et.id
        LEFT JOIN (
            SELECT egg_type_id, SUM(quantity) AS total_out
            FROM sales GROUP BY egg_type_id
        ) s ON s.egg_type_id = et.id
        ORDER BY et.name
    """).fetchall()
    conn.close()
    return rows


def get_stock_for_type(egg_type_id):
    """Tek bir yumurta çeşidinin stok miktarını döndürür."""
    conn = get_db()
    row = conn.execute("""
        SELECT
            et.initial_stock
            + COALESCE((SELECT SUM(quantity) FROM purchases WHERE egg_type_id = ?), 0)
            - COALESCE((SELECT SUM(quantity) FROM sales    WHERE egg_type_id = ?), 0)
            AS stock
        FROM egg_types et WHERE et.id = ?
    """, (egg_type_id, egg_type_id, egg_type_id)).fetchone()
    conn.close()
    return row["stock"] if row else 0


# ═══════════════════════════════════════════════════════════
#  TEDARİK (ALIŞ)
# ═══════════════════════════════════════════════════════════

def add_purchase(user_id, egg_type_id, supplier_id, quantity, unit_price, paid_amount, payment_method, date, note=""):
    total_price = quantity * unit_price
    if paid_amount is None or paid_amount < 0:
        paid_amount = total_price
    if not payment_method:
        payment_method = "Nakit"
    conn = get_db()
    conn.execute(
        """INSERT INTO purchases
           (user_id, egg_type_id, supplier_id, quantity, unit_price, total_price, paid_amount, payment_method, date, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, egg_type_id, supplier_id, quantity, unit_price, total_price, paid_amount, payment_method, date, note),
    )
    conn.commit()
    conn.close()


def update_purchase_payment(purchase_id, user_id, new_paid_amount, payment_method=None):
    conn = get_db()
    if payment_method:
        conn.execute(
            "UPDATE purchases SET paid_amount = ?, payment_method = ? WHERE id = ? AND user_id = ?",
            (new_paid_amount, payment_method, purchase_id, user_id)
        )
    else:
        conn.execute(
            "UPDATE purchases SET paid_amount = ? WHERE id = ? AND user_id = ?",
            (new_paid_amount, purchase_id, user_id)
        )
    conn.commit()
    conn.close()


def get_user_purchases(user_id, start_date=None, end_date=None):
    conn = get_db()
    query = """
        SELECT p.*, et.name AS egg_type_name, sup.name AS supplier_name,
               (p.total_price - p.paid_amount) AS remaining_debt
        FROM purchases p
        JOIN egg_types  et  ON et.id  = p.egg_type_id
        JOIN suppliers  sup ON sup.id = p.supplier_id
        WHERE p.user_id = ?
    """
    params = [user_id]
    if start_date:
        query += " AND p.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.date <= ?"
        params.append(end_date)
    query += " ORDER BY p.date DESC, p.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def delete_purchase(purchase_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM purchases WHERE id = ? AND user_id = ?", (purchase_id, user_id))
    conn.commit()
    conn.close()


def get_purchase_by_id(purchase_id):
    """Tek bir tedarik (alış) işleminin detayını getirir."""
    conn = get_db()
    row = conn.execute("""
        SELECT p.*, et.name AS egg_type_name, sup.name AS supplier_name,
               u.full_name AS user_name,
               (p.total_price - p.paid_amount) AS remaining_debt
        FROM purchases p
        JOIN egg_types et ON et.id = p.egg_type_id
        JOIN suppliers sup ON sup.id = p.supplier_id
        JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
    """, (purchase_id,)).fetchone()
    conn.close()
    return row


# ═══════════════════════════════════════════════════════════
#  SATIŞ
# ═══════════════════════════════════════════════════════════

def add_sale(user_id, egg_type_id, buyer_id, quantity, unit_price, paid_amount, payment_method, date, note=""):
    current_stock = get_stock_for_type(egg_type_id)
    if quantity > current_stock:
        return False, f"Yetersiz stok! Mevcut: {current_stock} adet"

    total_price = quantity * unit_price
    if paid_amount is None or paid_amount < 0:
        paid_amount = total_price
    if not payment_method:
        payment_method = "Nakit"
    conn = get_db()
    conn.execute(
        """INSERT INTO sales
           (user_id, egg_type_id, buyer_id, quantity, unit_price, total_price, paid_amount, payment_method, date, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, egg_type_id, buyer_id, quantity, unit_price, total_price, paid_amount, payment_method, date, note),
    )
    conn.commit()
    conn.close()
    return True, "Satış başarıyla kaydedildi."


def update_sale_payment(sale_id, user_id, new_paid_amount, payment_method=None):
    conn = get_db()
    if payment_method:
        conn.execute(
            "UPDATE sales SET paid_amount = ?, payment_method = ? WHERE id = ? AND user_id = ?",
            (new_paid_amount, payment_method, sale_id, user_id)
        )
    else:
        conn.execute(
            "UPDATE sales SET paid_amount = ? WHERE id = ? AND user_id = ?",
            (new_paid_amount, sale_id, user_id)
        )
    conn.commit()
    conn.close()
    conn.close()


def get_user_sales(user_id, start_date=None, end_date=None):
    conn = get_db()
    query = """
        SELECT s.*, et.name AS egg_type_name, b.name AS buyer_name,
               (s.total_price - s.paid_amount) AS remaining_receivable
        FROM sales s
        JOIN egg_types et ON et.id = s.egg_type_id
        JOIN buyers    b  ON b.id  = s.buyer_id
        WHERE s.user_id = ?
    """
    params = [user_id]
    if start_date:
        query += " AND s.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.date <= ?"
        params.append(end_date)
    query += " ORDER BY s.date DESC, s.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def delete_sale(sale_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM sales WHERE id = ? AND user_id = ?", (sale_id, user_id))
    conn.commit()
    conn.close()


def get_sale_by_id(sale_id):
    """Tek bir satış işleminin detayını getirir."""
    conn = get_db()
    row = conn.execute("""
        SELECT s.*, et.name AS egg_type_name, b.name AS buyer_name,
               u.full_name AS user_name,
               (s.total_price - s.paid_amount) AS remaining_receivable
        FROM sales s
        JOIN egg_types et ON et.id = s.egg_type_id
        JOIN buyers b ON b.id = s.buyer_id
        JOIN users u ON u.id = s.user_id
        WHERE s.id = ?
    """, (sale_id,)).fetchone()
    conn.close()
    return row


# ═══════════════════════════════════════════════════════════
#  CARİ HESAPLAR / BORÇ & ALACAK RAPORLARI
# ═══════════════════════════════════════════════════════════

def get_supplier_debts(user_id=None):
    """
    Hangi tedarikçiye ne kadar borç olduğunu firma bazında döndürür.
    user_id verilirse o kullanıcının alımları, verilmezse tüm deponun borçları.
    """
    conn = get_db()
    where = "WHERE p.user_id = ?" if user_id else ""
    params = [user_id] if user_id else []

    query = f"""
        SELECT
            sup.id,
            sup.name,
            COUNT(p.id) AS tx_count,
            COALESCE(SUM(p.total_price), 0) AS total_amount,
            COALESCE(SUM(p.paid_amount), 0) AS total_paid,
            COALESCE(SUM(p.total_price), 0) - COALESCE(SUM(p.paid_amount), 0) AS remaining_debt,
            MAX(p.date) AS last_date
        FROM suppliers sup
        JOIN purchases p ON p.supplier_id = sup.id
        {where}
        GROUP BY sup.id, sup.name
        ORDER BY remaining_debt DESC, sup.name ASC
    """
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_buyer_receivables(user_id=None):
    """
    Hangi alıcı firmadan ne kadar alacak olduğunu firma bazında döndürür.
    user_id verilirse o kullanıcının satışları, verilmezse tüm deponun alacakları.
    """
    conn = get_db()
    where = "WHERE s.user_id = ?" if user_id else ""
    params = [user_id] if user_id else []

    query = f"""
        SELECT
            b.id,
            b.name,
            COUNT(s.id) AS tx_count,
            COALESCE(SUM(s.total_price), 0) AS total_amount,
            COALESCE(SUM(s.paid_amount), 0) AS total_paid,
            COALESCE(SUM(s.total_price), 0) - COALESCE(SUM(s.paid_amount), 0) AS remaining_receivable,
            MAX(s.date) AS last_date
        FROM buyers b
        JOIN sales s ON s.buyer_id = b.id
        {where}
        GROUP BY b.id, b.name
        ORDER BY remaining_receivable DESC, b.name ASC
    """
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_pending_purchases(user_id=None):
    """Ödemesi eksik kalan alışları detaylı listeler."""
    conn = get_db()
    where = "WHERE (p.total_price - p.paid_amount) > 0.01"
    params = []
    if user_id:
        where += " AND p.user_id = ?"
        params.append(user_id)

    query = f"""
        SELECT p.*, et.name AS egg_type_name, sup.name AS supplier_name,
               (p.total_price - p.paid_amount) AS remaining_debt,
               u.full_name AS user_name
        FROM purchases p
        JOIN egg_types et ON et.id = p.egg_type_id
        JOIN suppliers sup ON sup.id = p.supplier_id
        JOIN users u ON u.id = p.user_id
        {where}
        ORDER BY p.date DESC
    """
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def get_pending_sales(user_id=None):
    """Tahsilatı eksik kalan satışları detaylı listeler."""
    conn = get_db()
    where = "WHERE (s.total_price - s.paid_amount) > 0.01"
    params = []
    if user_id:
        where += " AND s.user_id = ?"
        params.append(user_id)

    query = f"""
        SELECT s.*, et.name AS egg_type_name, b.name AS buyer_name,
               (s.total_price - s.paid_amount) AS remaining_receivable,
               u.full_name AS user_name
        FROM sales s
        JOIN egg_types et ON et.id = s.egg_type_id
        JOIN buyers b ON b.id = s.buyer_id
        JOIN users u ON u.id = s.user_id
        {where}
        ORDER BY s.date DESC
    """
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


# ═══════════════════════════════════════════════════════════
#  YÖNETİM: TEDARİKÇİ FİRMALAR
# ═══════════════════════════════════════════════════════════

def get_suppliers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return rows

def add_supplier(name):
    conn = get_db()
    try:
        conn.execute("INSERT INTO suppliers (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        return True, "Tedarikçi eklendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu tedarikçi zaten mevcut."

def update_supplier(sid, name):
    conn = get_db()
    try:
        conn.execute("UPDATE suppliers SET name = ? WHERE id = ?", (name, sid))
        conn.commit()
        conn.close()
        return True, "Tedarikçi güncellendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu isimde bir tedarikçi zaten var."

def delete_supplier(sid):
    conn = get_db()
    # Bağlı kayıt var mı kontrol et
    count = conn.execute("SELECT COUNT(*) FROM purchases WHERE supplier_id = ?", (sid,)).fetchone()[0]
    if count > 0:
        conn.close()
        return False, f"Bu tedarikçiye ait {count} alış kaydı var, silinemez."
    conn.execute("DELETE FROM suppliers WHERE id = ?", (sid,))
    conn.commit()
    conn.close()
    return True, "Tedarikçi silindi."


# ═══════════════════════════════════════════════════════════
#  YÖNETİM: ALICI FİRMALAR
# ═══════════════════════════════════════════════════════════

def get_buyers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM buyers ORDER BY name").fetchall()
    conn.close()
    return rows

def add_buyer(name):
    conn = get_db()
    try:
        conn.execute("INSERT INTO buyers (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        return True, "Alıcı firma eklendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu alıcı firma zaten mevcut."

def update_buyer(bid, name):
    conn = get_db()
    try:
        conn.execute("UPDATE buyers SET name = ? WHERE id = ?", (name, bid))
        conn.commit()
        conn.close()
        return True, "Alıcı firma güncellendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu isimde bir alıcı firma zaten var."

def delete_buyer(bid):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM sales WHERE buyer_id = ?", (bid,)).fetchone()[0]
    if count > 0:
        conn.close()
        return False, f"Bu alıcıya ait {count} satış kaydı var, silinemez."
    conn.execute("DELETE FROM buyers WHERE id = ?", (bid,))
    conn.commit()
    conn.close()
    return True, "Alıcı firma silindi."


# ═══════════════════════════════════════════════════════════
#  YÖNETİM: YUMURTA ÇEŞİTLERİ
# ═══════════════════════════════════════════════════════════

def get_egg_types():
    conn = get_db()
    rows = conn.execute("SELECT * FROM egg_types ORDER BY name").fetchall()
    conn.close()
    return rows

def add_egg_type(name, initial_stock=0):
    conn = get_db()
    try:
        conn.execute("INSERT INTO egg_types (name, initial_stock) VALUES (?, ?)", (name, initial_stock))
        conn.commit()
        conn.close()
        return True, "Yumurta çeşidi eklendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu yumurta çeşidi zaten mevcut."

def update_egg_type(eid, name, initial_stock):
    conn = get_db()
    try:
        conn.execute("UPDATE egg_types SET name = ?, initial_stock = ? WHERE id = ?",
                      (name, initial_stock, eid))
        conn.commit()
        conn.close()
        return True, "Yumurta çeşidi güncellendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu isimde bir çeşit zaten var."

def delete_egg_type(eid):
    conn = get_db()
    pc = conn.execute("SELECT COUNT(*) FROM purchases WHERE egg_type_id = ?", (eid,)).fetchone()[0]
    sc = conn.execute("SELECT COUNT(*) FROM sales WHERE egg_type_id = ?", (eid,)).fetchone()[0]
    if pc + sc > 0:
        conn.close()
        return False, f"Bu çeşide ait {pc} alış ve {sc} satış kaydı var, silinemez."
    conn.execute("DELETE FROM egg_types WHERE id = ?", (eid,))
    conn.commit()
    conn.close()
    return True, "Yumurta çeşidi silindi."


# ═══════════════════════════════════════════════════════════
#  YÖNETİM: KULLANICILAR
# ═══════════════════════════════════════════════════════════

def get_users():
    conn = get_db()
    rows = conn.execute("SELECT id, username, full_name FROM users ORDER BY full_name").fetchall()
    conn.close()
    return rows

def add_user(username, password, full_name):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
                      (username, _hash_pw(password), full_name))
        conn.commit()
        conn.close()
        return True, "Kullanıcı eklendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu kullanıcı adı zaten kullanımda."

def update_user(uid, username, full_name, password=None):
    conn = get_db()
    try:
        if password:
            conn.execute("UPDATE users SET username = ?, full_name = ?, password = ? WHERE id = ?",
                          (username, full_name, _hash_pw(password), uid))
        else:
            conn.execute("UPDATE users SET username = ?, full_name = ? WHERE id = ?",
                          (username, full_name, uid))
        conn.commit()
        conn.close()
        return True, "Kullanıcı güncellendi."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Bu kullanıcı adı zaten kullanımda."

def delete_user(uid):
    conn = get_db()
    pc = conn.execute("SELECT COUNT(*) FROM purchases WHERE user_id = ?", (uid,)).fetchone()[0]
    sc = conn.execute("SELECT COUNT(*) FROM sales WHERE user_id = ?", (uid,)).fetchone()[0]
    if pc + sc > 0:
        conn.close()
        return False, f"Bu kullanıcıya ait {pc} alış ve {sc} satış kaydı var, silinemez."
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    return True, "Kullanıcı silindi."


if __name__ == "__main__":
    init_db()
    print("Veritabanı başarıyla oluşturuldu.")
