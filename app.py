"""
Yumurta Depo Yönetim Sistemi - Ana Uygulama
Flask web uygulaması: giriş, stok, tedarik, satış, muhasebe, yönetim.
"""

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash,
)
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import date, timedelta
import database as db
import os

app = Flask(__name__)
# Sabit secret key (sunucu yeniden başlasa da oturumlar kaybolmaz)
app.secret_key = os.environ.get("SECRET_KEY", "yumurta-depo-guvenli-oturum-anahtari-2026-xyz789")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)  # 3 ay açık kalır
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ── Yardımcı ──────────────────────────────────────────────

def login_required(f):
    """Giriş yapmamış kullanıcıyı login sayfasına yönlendirir."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Lütfen önce giriş yapın.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Giriş / Çıkış ────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        conn = db.get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            remember = request.form.get("remember")
            if remember:
                session.permanent = True
            else:
                session.permanent = False

            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            flash(f"Hoş geldin, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Kullanıcı adı veya şifre hatalı.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for("login"))


# ── Ana Sayfa / Stok ─────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    stock = db.get_stock()
    conn = db.get_db()

    recent_purchases = conn.execute("""
        SELECT p.*, et.name AS egg_type_name, sup.name AS supplier_name
        FROM purchases p
        JOIN egg_types et  ON et.id  = p.egg_type_id
        JOIN suppliers sup ON sup.id = p.supplier_id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC LIMIT 5
    """, (session["user_id"],)).fetchall()

    recent_sales = conn.execute("""
        SELECT s.*, et.name AS egg_type_name, b.name AS buyer_name
        FROM sales s
        JOIN egg_types et ON et.id = s.egg_type_id
        JOIN buyers    b  ON b.id  = s.buyer_id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC LIMIT 5
    """, (session["user_id"],)).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        stock=stock,
        recent_purchases=recent_purchases,
        recent_sales=recent_sales,
    )


# ── Tedarik (Alış) ───────────────────────────────────────

@app.route("/tedarik", methods=["GET", "POST"])
@login_required
def tedarik():
    egg_types = db.get_egg_types()
    suppliers = db.get_suppliers()

    if request.method == "POST":
        try:
            egg_type_id = int(request.form["egg_type_id"])
            supplier_id = int(request.form["supplier_id"])
            quantity = int(request.form["quantity"])
            unit_price = float(request.form["unit_price"])
            total = quantity * unit_price
            paid_str = request.form.get("paid_amount", "").strip()
            paid_amount = float(paid_str) if paid_str else total
            payment_method = request.form.get("payment_method", "Nakit").strip()
            purchase_date = request.form["date"]
            note = request.form.get("note", "").strip()

            if quantity <= 0:
                flash("Miktar sıfırdan büyük olmalı.", "warning")
            elif unit_price < 0:
                flash("Birim fiyat negatif olamaz.", "warning")
            elif paid_amount < 0:
                flash("Ödenen tutar negatif olamaz.", "warning")
            else:
                db.add_purchase(
                    session["user_id"], egg_type_id, supplier_id,
                    quantity, unit_price, paid_amount, payment_method, purchase_date, note
                )
                sup_name = next((s["name"] for s in suppliers if s["id"] == supplier_id), "?")
                debt = total - paid_amount
                debt_info = f" (Kalan Borç: {debt:.2f} ₺)" if debt > 0 else " (Tamamı Ödendi)"
                method_icon = "💳 Kart" if payment_method == "Kart" else "💵 Nakit"
                flash(
                    f"✅ Tedarik kaydedildi: {sup_name}'dan {quantity} adet × "
                    f"{unit_price:.2f} ₺ = {total:.2f} ₺ [{method_icon}]{debt_info}",
                    "success",
                )
                return redirect(url_for("tedarik"))
        except (ValueError, KeyError) as e:
            flash(f"Geçersiz veri: {e}", "danger")

    purchases = db.get_user_purchases(session["user_id"])
    return render_template(
        "tedarik.html",
        egg_types=egg_types,
        suppliers=suppliers,
        purchases=purchases,
        today=date.today().isoformat(),
    )


# ── Satış ─────────────────────────────────────────────────

@app.route("/satis", methods=["GET", "POST"])
@login_required
def satis():
    egg_types = db.get_egg_types()
    buyers = db.get_buyers()
    stock = db.get_stock()

    if request.method == "POST":
        try:
            egg_type_id = int(request.form["egg_type_id"])
            buyer_id = int(request.form["buyer_id"])
            quantity = int(request.form["quantity"])
            unit_price = float(request.form["unit_price"])
            total = quantity * unit_price
            paid_str = request.form.get("paid_amount", "").strip()
            paid_amount = float(paid_str) if paid_str else total
            payment_method = request.form.get("payment_method", "Nakit").strip()
            sale_date = request.form["date"]
            note = request.form.get("note", "").strip()

            if quantity <= 0:
                flash("Miktar sıfırdan büyük olmalı.", "warning")
            elif unit_price < 0:
                flash("Birim fiyat negatif olamaz.", "warning")
            elif paid_amount < 0:
                flash("Tahsil edilen tutar negatif olamaz.", "warning")
            else:
                ok, msg = db.add_sale(
                    session["user_id"], egg_type_id, buyer_id,
                    quantity, unit_price, paid_amount, payment_method, sale_date, note
                )
                if ok:
                    buyer_name = next((b["name"] for b in buyers if b["id"] == buyer_id), "?")
                    receivable = total - paid_amount
                    rec_info = f" (Kalan Alacak: {receivable:.2f} ₺)" if receivable > 0 else " (Tamamı Tahsil Edildi)"
                    method_icon = "💳 Kart" if payment_method == "Kart" else "💵 Nakit"
                    flash(
                        f"✅ Satış kaydedildi: {buyer_name}'a {quantity} adet × "
                        f"{unit_price:.2f} ₺ = {total:.2f} ₺ [{method_icon}]{rec_info}",
                        "success",
                    )
                    return redirect(url_for("satis"))
                else:
                    flash(msg, "danger")
        except (ValueError, KeyError) as e:
            flash(f"Geçersiz veri: {e}", "danger")

    sales = db.get_user_sales(session["user_id"])
    return render_template(
        "satis.html",
        egg_types=egg_types,
        buyers=buyers,
        sales=sales,
        stock=stock,
        today=date.today().isoformat(),
    )


# ── Tekil İşlem Fişi Yazdırma ────────────────────────────

@app.route("/yazdir/tedarik/<int:pid>")
@login_required
def print_purchase(pid):
    purchase = db.get_purchase_by_id(pid)
    if not purchase:
        flash("Tedarik kaydı bulunamadı.", "danger")
        return redirect(url_for("tedarik"))
    return render_template(
        "islem_fisi.html",
        tx_type="tedarik",
        tx=purchase,
        today=date.today().isoformat(),
    )


@app.route("/yazdir/satis/<int:sid>")
@login_required
def print_sale(sid):
    sale = db.get_sale_by_id(sid)
    if not sale:
        flash("Satış kaydı bulunamadı.", "danger")
        return redirect(url_for("satis"))
    return render_template(
        "islem_fisi.html",
        tx_type="satis",
        tx=sale,
        today=date.today().isoformat(),
    )


# ── Muhasebe Raporu ───────────────────────────────────────

@app.route("/muhasebe", methods=["GET", "POST"])
@login_required
def muhasebe():
    start_date = request.form.get("start_date") or request.args.get("start_date")
    end_date = request.form.get("end_date") or request.args.get("end_date")

    purchases = db.get_user_purchases(session["user_id"], start_date, end_date)
    sales = db.get_user_sales(session["user_id"], start_date, end_date)

    total_purchase_amount = sum(p["total_price"] for p in purchases)
    total_purchase_paid = sum(p["paid_amount"] for p in purchases)
    total_purchase_debt = total_purchase_amount - total_purchase_paid
    total_purchase_qty = sum(p["quantity"] for p in purchases)

    total_sale_amount = sum(s["total_price"] for s in sales)
    total_sale_collected = sum(s["paid_amount"] for s in sales)
    total_sale_receivable = total_sale_amount - total_sale_collected
    total_sale_qty = sum(s["quantity"] for s in sales)

    profit = total_sale_amount - total_purchase_amount

    # Nakit / Kart ayrımı
    purchase_cash = sum(p["paid_amount"] for p in purchases if p["payment_method"] == "Nakit")
    purchase_card = sum(p["paid_amount"] for p in purchases if p["payment_method"] == "Kart")
    sale_cash = sum(s["paid_amount"] for s in sales if s["payment_method"] == "Nakit")
    sale_card = sum(s["paid_amount"] for s in sales if s["payment_method"] == "Kart")

    # Çeşit bazında özet
    type_summary = {}
    for p in purchases:
        name = p["egg_type_name"]
        if name not in type_summary:
            type_summary[name] = {"bought_qty": 0, "bought_amount": 0, "sold_qty": 0, "sold_amount": 0}
        type_summary[name]["bought_qty"] += p["quantity"]
        type_summary[name]["bought_amount"] += p["total_price"]
    for s in sales:
        name = s["egg_type_name"]
        if name not in type_summary:
            type_summary[name] = {"bought_qty": 0, "bought_amount": 0, "sold_qty": 0, "sold_amount": 0}
        type_summary[name]["sold_qty"] += s["quantity"]
        type_summary[name]["sold_amount"] += s["total_price"]

    return render_template(
        "muhasebe.html",
        purchases=purchases,
        sales=sales,
        start_date=start_date or "",
        end_date=end_date or "",
        total_purchase_amount=total_purchase_amount,
        total_purchase_paid=total_purchase_paid,
        total_purchase_debt=total_purchase_debt,
        total_purchase_qty=total_purchase_qty,
        purchase_cash=purchase_cash,
        purchase_card=purchase_card,
        total_sale_amount=total_sale_amount,
        total_sale_collected=total_sale_collected,
        total_sale_receivable=total_sale_receivable,
        total_sale_qty=total_sale_qty,
        sale_cash=sale_cash,
        sale_card=sale_card,
        profit=profit,
        type_summary=type_summary,
        today=date.today().isoformat(),
        report_generated=bool(start_date or end_date),
    )


# ── Borç & Alacak (Cari Hesaplar) ──────────────────────────

@app.route("/borc-alacak")
@login_required
def borc_alacak():
    # Görünüm modu: 'all' (Tüm Depo) veya 'my' (Sadece Benim)
    view_mode = request.args.get("view", "all")
    uid = session["user_id"] if view_mode == "my" else None

    supplier_debts = db.get_supplier_debts(uid)
    buyer_receivables = db.get_buyer_receivables(uid)
    pending_purchases = db.get_pending_purchases(uid)
    pending_sales = db.get_pending_sales(uid)

    total_debt = sum(s["remaining_debt"] for s in supplier_debts)
    total_receivable = sum(b["remaining_receivable"] for b in buyer_receivables)
    net_balance = total_receivable - total_debt  # Pozitifse alacaklıyız, negatifse borçluyuz

    return render_template(
        "borc_alacak.html",
        supplier_debts=supplier_debts,
        buyer_receivables=buyer_receivables,
        pending_purchases=pending_purchases,
        pending_sales=pending_sales,
        total_debt=total_debt,
        total_receivable=total_receivable,
        net_balance=net_balance,
        view_mode=view_mode,
    )


# ── Ödeme / Tahsilat Güncelle ─────────────────────────────

@app.route("/odeme-guncelle/tedarik/<int:pid>", methods=["POST"])
@login_required
def update_purchase_payment(pid):
    try:
        new_paid = float(request.form.get("paid_amount", 0))
        method = request.form.get("payment_method")
        if new_paid < 0:
            flash("Ödenen tutar negatif olamaz.", "warning")
        else:
            db.update_purchase_payment(pid, session["user_id"], new_paid, method)
            flash("Tedarik ödeme tutarı güncellendi.", "success")
    except ValueError:
        flash("Geçersiz ödeme tutarı.", "danger")
    return redirect(request.referrer or url_for("borc_alacak"))


@app.route("/tahsilat-guncelle/satis/<int:sid>", methods=["POST"])
@login_required
def update_sale_payment(sid):
    try:
        new_paid = float(request.form.get("paid_amount", 0))
        method = request.form.get("payment_method")
        if new_paid < 0:
            flash("Tahsil edilen tutar negatif olamaz.", "warning")
        else:
            db.update_sale_payment(sid, session["user_id"], new_paid, method)
            flash("Satış tahsilat tutarı güncellendi.", "success")
    except ValueError:
        flash("Geçersiz tahsilat tutarı.", "danger")
    return redirect(request.referrer or url_for("borc_alacak"))


# ── Kayıt Silme ──────────────────────────────────────────

@app.route("/sil/tedarik/<int:pid>", methods=["POST"])
@login_required
def delete_purchase(pid):
    db.delete_purchase(pid, session["user_id"])
    flash("Tedarik kaydı silindi.", "info")
    return redirect(request.referrer or url_for("tedarik"))


@app.route("/sil/satis/<int:sid>", methods=["POST"])
@login_required
def delete_sale(sid):
    db.delete_sale(sid, session["user_id"])
    flash("Satış kaydı silindi.", "info")
    return redirect(request.referrer or url_for("satis"))


# ═══════════════════════════════════════════════════════════
#  YÖNETİM PANELİ
# ═══════════════════════════════════════════════════════════

@app.route("/yonetim")
@login_required
def yonetim():
    return render_template(
        "yonetim.html",
        suppliers=db.get_suppliers(),
        buyers=db.get_buyers(),
        egg_types=db.get_egg_types(),
        users=db.get_users(),
        stock=db.get_stock(),
    )


# ── Tedarikçi CRUD ───────────────────────────────────────

@app.route("/yonetim/tedarikci/ekle", methods=["POST"])
@login_required
def add_supplier():
    name = request.form.get("name", "").strip()
    if name:
        ok, msg = db.add_supplier(name)
        flash(msg, "success" if ok else "warning")
    else:
        flash("Firma adı boş olamaz.", "warning")
    return redirect(url_for("yonetim") + "#tedarikciler")


@app.route("/yonetim/tedarikci/guncelle/<int:sid>", methods=["POST"])
@login_required
def update_supplier(sid):
    name = request.form.get("name", "").strip()
    if name:
        ok, msg = db.update_supplier(sid, name)
        flash(msg, "success" if ok else "warning")
    return redirect(url_for("yonetim") + "#tedarikciler")


@app.route("/yonetim/tedarikci/sil/<int:sid>", methods=["POST"])
@login_required
def delete_supplier(sid):
    ok, msg = db.delete_supplier(sid)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("yonetim") + "#tedarikciler")


# ── Alıcı CRUD ───────────────────────────────────────────

@app.route("/yonetim/alici/ekle", methods=["POST"])
@login_required
def add_buyer():
    name = request.form.get("name", "").strip()
    if name:
        ok, msg = db.add_buyer(name)
        flash(msg, "success" if ok else "warning")
    else:
        flash("Firma adı boş olamaz.", "warning")
    return redirect(url_for("yonetim") + "#alicilar")


@app.route("/yonetim/alici/guncelle/<int:bid>", methods=["POST"])
@login_required
def update_buyer(bid):
    name = request.form.get("name", "").strip()
    if name:
        ok, msg = db.update_buyer(bid, name)
        flash(msg, "success" if ok else "warning")
    return redirect(url_for("yonetim") + "#alicilar")


@app.route("/yonetim/alici/sil/<int:bid>", methods=["POST"])
@login_required
def delete_buyer(bid):
    ok, msg = db.delete_buyer(bid)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("yonetim") + "#alicilar")


# ── Yumurta Çeşidi CRUD ──────────────────────────────────

@app.route("/yonetim/cesit/ekle", methods=["POST"])
@login_required
def add_egg_type():
    name = request.form.get("name", "").strip()
    initial_stock = int(request.form.get("initial_stock", 0) or 0)
    if name:
        ok, msg = db.add_egg_type(name, initial_stock)
        flash(msg, "success" if ok else "warning")
    else:
        flash("Çeşit adı boş olamaz.", "warning")
    return redirect(url_for("yonetim") + "#cesitler")


@app.route("/yonetim/cesit/guncelle/<int:eid>", methods=["POST"])
@login_required
def update_egg_type(eid):
    name = request.form.get("name", "").strip()
    initial_stock = int(request.form.get("initial_stock", 0) or 0)
    if name:
        ok, msg = db.update_egg_type(eid, name, initial_stock)
        flash(msg, "success" if ok else "warning")
    return redirect(url_for("yonetim") + "#cesitler")


@app.route("/yonetim/cesit/sil/<int:eid>", methods=["POST"])
@login_required
def delete_egg_type(eid):
    ok, msg = db.delete_egg_type(eid)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("yonetim") + "#cesitler")


# ── Kullanıcı CRUD ───────────────────────────────────────

@app.route("/yonetim/kullanici/ekle", methods=["POST"])
@login_required
def add_user():
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "")
    if not username or not full_name or not password:
        flash("Tüm alanları doldurun.", "warning")
    else:
        ok, msg = db.add_user(username, password, full_name)
        flash(msg, "success" if ok else "warning")
    return redirect(url_for("yonetim") + "#kullanicilar")


@app.route("/yonetim/kullanici/guncelle/<int:uid>", methods=["POST"])
@login_required
def update_user(uid):
    username = request.form.get("username", "").strip().lower()
    full_name = request.form.get("full_name", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not full_name:
        flash("Kullanıcı adı ve isim boş olamaz.", "warning")
    else:
        ok, msg = db.update_user(uid, username, full_name, password if password else None)
        flash(msg, "success" if ok else "warning")
    return redirect(url_for("yonetim") + "#kullanicilar")


@app.route("/yonetim/kullanici/sil/<int:uid>", methods=["POST"])
@login_required
def delete_user(uid):
    if uid == session.get("user_id"):
        flash("Kendinizi silemezsiniz!", "danger")
    else:
        ok, msg = db.delete_user(uid)
        flash(msg, "success" if ok else "danger")
    return redirect(url_for("yonetim") + "#kullanicilar")


# ── Başlatma ──────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, host="0.0.0.0", port=5050)
