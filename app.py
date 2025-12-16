from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, event
from config import Config
from config import *
from datetime import datetime
from datetime import date, timedelta
from collections import defaultdict
import math
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)

# lokasi simpan gambar
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'products')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# -------------------------
# Models
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  
    role = db.Column(db.String(32), nullable=False) 

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    sku = db.Column(db.String(64), unique=True, nullable=True) 
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(64), nullable=True)
    stock = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(255), nullable=True)  

def save_image(file):
    if not file:
        return None

    filename = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return filename


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    qty = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')

class Return(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    qty = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(140), unique=True, nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------
# DB init / seed
# -------------------------
def init_db():
    os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)
    db.create_all()
    # seed users & sample products if not exist
    if not User.query.first():
        db.session.add_all([
            User(username='owner', password='password', role='owner'),
            User(username='kasir', password='password', role='kasir'),
            User(username='marketing', password='password', role='marketing'),
        ])
        db.session.commit()
    if not Product.query.first():
        sample = [
            Product(name='Helm Full Face A', sku='HF-A-001', price=650000, category='Premium', stock=10),
            Product(name='Helm Half Face B', sku='HH-B-002', price=250000, category='Menengah', stock=15),
            Product(name='Visor Clear', sku='VS-C-010', price=50000, category='Aksesoris', stock=40),
        ]
        db.session.add_all(sample)
        db.session.commit()

# -------------------------
# Helpers
# -------------------------
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return wrapper

def is_owner():
    return session.get("role") == "owner"

def is_staff():
    return session.get("role") == "staff"

def is_developer():
    return session.get("role") == "developer"

def exponential_smoothing(data, alpha=0.3):
    if not data:
        return []

    result = [data[0]]
    for i in range(1, len(data)):
        result.append(alpha * data[i] + (1 - alpha) * result[i-1])
    return result

def moving_average(data, window=3):
    if len(data) < window:
        return []

    return [
        round(sum(data[i-window:i]) / window)
        for i in range(window, len(data)+1)
    ]

import math

def calculate_rop(daily_demand, lead_time):
    return math.ceil(daily_demand * lead_time)

def calculate_eoq(annual_demand, order_cost, holding_cost):
    if annual_demand == 0 or holding_cost == 0:
        return 0
    return math.ceil(
        math.sqrt((2 * annual_demand * order_cost) / holding_cost)
    )

# -------------------------
# Routes
# -------------------------
@app.route('/')
def index():
    if current_user():
        return redirect(url_for('dashboard'))
    return render_template('landing/landing.html', title="Landing Page", active_page="index")

@app.route('/beranda')
def beranda():
    return render_template("landing/landing.html", active_page="beranda")

@app.route('/tentang')
def tentang():
    return render_template("landing/tentang.html", active_page="tentang")

@app.route('/produk')
def produk():
    return render_template("landing/produk.html", active_page="produk")

@app.route('/kontak')
def kontak():
    return render_template("landing/kontak.html", active_page="kontak")

@app.route("/search")
def search():
    q = request.args.get("q", "")

    # Redirect ke kategori SEMUA dengan query pencarian
    return redirect(url_for("category_page", category_name="Semua", q=q))

CATEGORIES = ["Semua", "New Arrival", "Aksesoris", "Half Face", "Wanita", "Full Face"]
@app.route('/category/<category_name>')
def category_page(category_name):
    q = request.args.get("q", "").lower()

    # Ambil produk berdasarkan kategori
    if category_name.lower() == "semua":
        products = Product.query.all()
    else:
        products = Product.query.filter(
            db.func.lower(Product.category) == category_name.lower()
        ).all()

    # Filter hasil search
    if q:
        products = [p for p in products if q in p.name.lower()]

    return render_template(
        "landing/category.html",
        category=category_name,
        categories=CATEGORIES,
        products=products,
        active_page="category_page",
        q=q
    )

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        user = User.query.filter_by(username=u, password=p).first()
        if user:
            session['user_id'] = user.id
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(ok=True, next=url_for('dashboard'))
            flash(f'Logged in as {user.username}', 'success')
            return redirect(url_for('dashboard'))
        # gagal
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(ok=False, error='Username atau password salah'), 401
        flash('Username atau password salah', 'danger')
        return redirect(url_for('login'))
    return render_template('system/login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()  # Sesuai sistem auth kamu (mungkin user_loader / flask_login)

    product_preview = Product.query.order_by(Product.id.desc()).limit(6).all()
    total_products = Product.query.count()
    total_stock = db.session.query(db.func.sum(Product.stock)).scalar() or 0
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()

    # === BULANAN ===
    monthly = (
        db.session.query(
            func.date_format(Sale.created_at, "%Y-%m").label("month"),
            func.sum(Sale.total).label("revenue")
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    nama_bulan_indo = {
        "01": "Januari", "02": "Februari", "03": "Maret", "04": "April",
        "05": "Mei", "06": "Juni", "07": "Juli", "08": "Agustus",
        "09": "September", "10": "Oktober", "11": "November", "12": "Desember"
    }

    # m[0] contoh: "2025-01"
    # kita ambil bagian bulan = m[0][5:7]
    months = [nama_bulan_indo.get(m[0][5:7], m[0]) for m in monthly]
    revenue = [m[1] for m in monthly]

    total_sales = db.session.query(db.func.sum(Sale.total)).scalar() or 0
    total_orders = db.session.query(db.func.count(Sale.id)).scalar() or 0
    net_profit = total_sales * 0.2

    return render_template(
        "system/dashboard.html",
        user=user,
        role=user.role,              # <=== Tambahkan ini
        products=product_preview,
        total_products=total_products,
        total_stock=total_stock,
        recent_sales=recent_sales,
        total_sales=total_sales,
        total_orders=total_orders,
        net_profit=net_profit,
        dashboard_data={
            "months": months,
            "revenue": revenue
        },
        title="Dashboard"
    )


# Products
@app.route('/products')
@login_required
def products():
    user = current_user()
    q = request.args.get("search", "").strip()

    if q:
        # filter berdasarkan nama, sku, atau kategori (opsional)
        items = Product.query.filter(
            (Product.name.ilike(f"%{q}%")) |
            (Product.sku.ilike(f"%{q}%")) |
            (Product.category.ilike(f"%{q}%"))
        ).order_by(Product.name).all()
    else:
        items = Product.query.order_by(Product.name).all()

    return render_template(
        'system/products.html',
        user=user,
        role=user.role,
        products=items,
        title="Data Produk",
        search=q  # kirim balik ke template
    )

UPLOAD_FOLDER = 'static/uploads/products'
ALLOWED_EXT = {'png','jpg','jpeg','webp'}

def allowed(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/products/add', methods=['POST'])
@login_required
def add_product():
    if is_owner(): 
        flash("Owner tidak bisa menambah produk.", "danger")
        return redirect(url_for('products'))
    name = request.form.get('name')
    sku = request.form.get('sku') or None
    price = float(request.form.get('price') or 0)
    category = request.form.get('category')
    stock = int(request.form.get('stock') or 0)
    desc = request.form.get('description')

    image_file = request.files.get('image')
    image_filename = None

    if image_file and allowed(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(image_path)
        image_filename = filename

    p = Product(
        name=name,
        sku=sku,
        price=price,
        category=category,
        stock=stock,
        description=desc,
        image=image_filename
    )

    db.session.add(p)
    db.session.commit()

    flash('Product added', 'success')
    return redirect(url_for('products'))

@app.get("/product/<int:id>/edit")
def product_edit(id):
    if is_owner():
        flash("Owner tidak bisa menghapus produk.", "danger")
        return redirect(url_for('products'))
    product = Product.query.get_or_404(id)
    return render_template("system/product_edit_form.html", p=product)


@app.route('/products/<int:id>/update', methods=['POST'])
@login_required
def update_product(id):
    p = Product.query.get_or_404(id)

    p.name = request.form.get('name')
    p.sku = request.form.get('sku') or p.sku
    p.price = float(request.form.get('price') or p.price)
    p.category = request.form.get('category') or p.category
    p.stock = int(request.form.get('stock') or p.stock)
    p.description = request.form.get('description') or p.description

    image_file = request.files.get('image')
    if image_file and allowed(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(image_path)
        p.image = filename

    db.session.commit()
    flash('Product updated', 'success')
    return redirect(url_for('products'))

@app.route('/products/<int:id>/delete', methods=['POST'])
@login_required
def delete_product(id):
    p = Product.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash('Product deleted', 'warning')
    return redirect(url_for('products'))

# Sales
@app.route('/sales')
@login_required
def sales():
    user = current_user()
    items = Product.query.order_by(Product.name).all()
    sales = Sale.query.order_by(Sale.created_at.desc()).limit(50).all()
    return render_template(
        'system/sales.html', 
        products=items, 
        sales=sales,
        user=user,
        role=user.role, 
        title="Data Penjualan")

@app.route('/sales/add', methods=['POST'])
@login_required
def add_sale():
    if is_owner():
        flash("Owner tidak bisa menghapus produk.", "danger")
        return redirect(url_for('sales'))
    pid = int(request.form.get('product_id'))
    qty = int(request.form.get('qty') or 1)
    created_str = request.form.get('created_at')

    # PARSE datetime-local input → format: "2025-03-01T14:30"
    created_at = datetime.strptime(created_str, "%Y-%m-%dT%H:%M")

    p = Product.query.get_or_404(pid)

    if p.stock < qty:
        flash('Not enough stock', 'danger')
        return redirect(url_for('sales'))

    total = p.price * qty
    p.stock -= qty

    sale = Sale(product_id=pid, qty=qty, total=total, created_at=created_at)
    db.session.add(sale)
    db.session.commit()

    flash('Sale recorded', 'success')
    return redirect(url_for('sales'))


# Returns
@app.route('/returns')
@login_required
def returns():
    user = current_user()
    items = Return.query.order_by(Return.created_at.desc()).limit(50).all()
    products = Product.query.order_by(Product.name).all()
    return render_template(
        'system/returns.html',
        user=user,
        role=user.role, 
        returns=items, 
        products=products, 
        title="Data Retur")

@app.route('/returns/add', methods=['POST'])
@login_required
def add_return():
    if is_owner():
        flash("Owner tidak bisa menghapus produk.", "danger")
        return redirect(url_for('returns'))
    pid = int(request.form.get('product_id'))
    qty = int(request.form.get('qty') or 1)
    reason = request.form.get('reason')
    p = Product.query.get_or_404(pid)
    # for demo, returns add back to stock
    p.stock += qty
    r = Return(product_id=pid, qty=qty, reason=reason)
    db.session.add(r)
    db.session.commit()
    flash('Return recorded', 'info')
    return redirect(url_for('returns'))

# Reports
@app.route('/reports')
@login_required
def reports():
    user = current_user()

    # 1. PERSIAPAN DATA (STOK)
    products = Product.query.all()
    
    # Ambil history penjualan untuk Forecast
    sales_query = (
        db.session.query(
            Sale.product_id,
            func.date_format(Sale.created_at, '%Y-%m').label('month'),
            func.sum(Sale.qty)
        )
        .group_by(Sale.product_id, 'month')
        .order_by('month')
        .all()
    )

    product_sales_history = defaultdict(list)
    for pid, month, total_qty in sales_query:
        product_sales_history[pid].append(float(total_qty or 0))

    inventory_report = []

    # 2. LOOPING PER PRODUK
    for p in products:
        qty_history = product_sales_history.get(p.id, [])
        
        # --- FORECAST ---
        next_forecast = 0
        has_data = False 
        
        if len(qty_history) >= 2:
            ses = exponential_smoothing(qty_history, alpha=0.3)
            next_forecast = math.ceil(ses[-1])
            has_data = True
        elif len(qty_history) == 1:
            next_forecast = math.ceil(qty_history[0])
            has_data = True
        else:
            next_forecast = 0
            has_data = False 

        # --- ROP & EOQ ---
        rop = 0
        eoq = 0
        
        if next_forecast > 0:
            daily_demand = next_forecast / WORKING_DAYS
            annual_demand = next_forecast * 12
            rop = math.ceil(daily_demand * LEAD_TIME_DAYS)
            
            holding_cost = p.price * HOLDING_RATE
            if holding_cost > 0:
                eoq = math.ceil(math.sqrt((2 * annual_demand * ORDER_COST) / holding_cost))

        # --- STATUS ---
        status = ""
        action = ""
        status_class = ""
        
        if not has_data:
            if p.stock > 0:
                status = "Produk Baru"
                action = "Monitor Penjualan"
                status_class = "info"
            else:
                status = "Stok Kosong"
                action = "Input Stok Awal"
                status_class = "warning"
        else:
            if p.stock <= rop:
                status = "Bahaya"
                buy_qty = int(eoq) if eoq > 0 else 10 
                action = f"ORDER {buy_qty} pcs"
                status_class = "danger"
            elif p.stock > (rop + (eoq * 2)) and eoq > 0:
                 status = "Overstock"
                 action = "Stop Order"
                 status_class = "success"
            else:
                 status = "Aman"
                 action = "-"
                 status_class = "success"

        inventory_report.append({
            'name': p.name,
            'sku': p.sku,
            'price': p.price,
            'stock': p.stock,
            'forecast': next_forecast,
            'rop': rop,
            'eoq': eoq,
            'status': status,
            'action': action,
            'status_class': status_class
        })

    # 3. DATA PENDUKUNG    
    all_sales = Sale.query.all()
    # DEBUG: Cek Terminal Anda saat refresh halaman reports
    print(f"DEBUG SYSTEM: Ditemukan {len(all_sales)} transaksi penjualan.")
    revenue_map = defaultdict(float)

    for s in all_sales:
        if s.created_at: # Pastikan tanggal tidak null
            # Format bulan YYYY-MM
            month_key = s.created_at.strftime('%Y-%m')
            
            # Gunakan kolom 'total' yang tersimpan di Sale
            # Ini lebih aman daripada mengalikan ulang dengan harga produk sekarang
            nominal = float(s.total or 0)
            
            revenue_map[month_key] += nominal

    sales_chart_data = sorted([(k, v) for k, v in revenue_map.items()])

    sales = db.session.query(func.date_format(Sale.created_at, "%Y-%m").label("month"),
                             func.sum(Sale.total).label('total')).group_by('month').order_by('month').all()
    top_products = db.session.query(Product.name, func.sum(Sale.qty).label('sold'))\
                    .join(Sale, Sale.product_id == Product.id)\
                    .group_by(Product.id).order_by(func.sum(Sale.qty).desc()).limit(10).all()

    # DEBUG: Cek hasil grouping
    print(f"DEBUG SYSTEM: Data Chart = {sales_chart_data}")

    top_products_query = (
        db.session.query(
            Product.name,
            func.sum(Sale.qty).label("sold")
        )
        .join(Sale, Sale.product_id == Product.id) # Inner join standard
        .group_by(Product.id)
        .order_by(func.sum(Sale.qty).desc())
        .limit(10)
        .all()
    )
    top_products = [(n, int(s or 0)) for n, s in top_products_query]

    # 4. RENDER TEMPLATE
    return render_template(
        'system/reports.html',
        user=user,
        role=user.role,            
        inventory_report=inventory_report,
        sales=sales,
        sales_chart_data=sales_chart_data,
        top_products=top_products,
        title="Laporan & Analisis Stok"
    )

#staff
def get_sidebar_menu():
    role = session.get('role')

    menu = [
        {"name": "Dashboard", "url": "dashboard"},
        {"name": "Penjualan", "url": "penjualan"},
        {"name": "Stok", "url": "stok"},
    ]

    if role in ["owner", "developer"]:
        menu.append({"name": "Manajemen Staff", "url": "manajemen_staff"})

    return menu

@app.route('/staff')
@login_required
def staff_page():
    user = current_user()
    staff_list = Staff.query.order_by(Staff.name).all()

    return render_template(
        "system/staff.html",
        user=user,
        role=user.role,
        staff=staff_list,
        title="Manajemen Staff"
    )

@app.route('/staff/add', methods=['GET', 'POST'])
@login_required
def add_staff():
    name = request.form.get('staff_name')
    role = request.form.get('role')
    email = request.form.get('email')
    phone = request.form.get('phone')
    created_at_raw = request.form.get('created_at')

    if created_at_raw:
        try:
            # Convert dari format datetime-local HTML
            created_at = datetime.strptime(created_at_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            created_at = datetime.utcnow()
    else:
        created_at = datetime.utcnow()

    image_file = request.files.get('staff_image')
    image_filename = None

    if image_file and allowed(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(image_path)
        image_filename = filename

    s = Staff(
        name=name,
        role=role,
        email=email,
        phone=phone,
        created_at=created_at
    )

    db.session.add(s)
    db.session.commit()

    flash('Staff added', 'success')
    return redirect(url_for('staff_page'))

@app.get("/staff/<int:id>/edit")
def staff_edit(id):
    staff = Staff.query.get_or_404(id)
    return render_template("system/staff_edit_form.html", s=staff)


@app.route('/staff/<int:id>/update', methods=['POST'])
@login_required
def update_staff(id):
    s = Staff.query.get_or_404(id)

    s.name = request.form.get('staff_name') or s.name
    s.role = request.form.get('role') or s.role
    s.email = request.form.get('email') or s.email
    s.phone = request.form.get('phone') or s.phone
    s.created_at = request.form.get('created_at') or s.created_at

    db.session.commit()
    flash('Staff updated', 'success')
    return redirect(url_for('staff_page'))

@app.route('/staff/<int:id>/delete', methods=['POST'])
@login_required
def delete_staff(id):
    s = Staff.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    flash('Staff deleted', 'warning')
    return redirect(url_for('staff_page'))

@event.listens_for(Staff, "after_insert")
def create_user_after_staff_insert(mapper, connection, staff):
    # Buat username otomatis dari email atau name
    username = staff.name.lower().replace(" ", "")

    connection.execute(
        User.__table__.insert().values(
            username=username,
            password="123",
            role=staff.role
        )
    )

@event.listens_for(Staff, "after_update")
def update_user_after_staff_update(mapper, connection, staff):
    if not staff.email:
        return

    user = User.query.filter_by(username=staff.email).first()
    if user:
        user.role = staff.role
        # Email/username berubah? Atur jika perlu
        # user.username = staff.email
        db.session.commit()

@event.listens_for(Staff, "after_delete")
def delete_user_after_staff_delete(mapper, connection, staff):
    if not staff.email:
        return

    user = User.query.filter_by(username=staff.email).first()
    if user:
        db.session.delete(user)
        db.session.commit()

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    # pastikan user sudah login
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # cek password lama
        if user.password != old_password:
            flash("Password lama salah!", "danger")
            return redirect(url_for("change_password"))

        # cek konfirmasi password
        if new_password != confirm_password:
            flash("Password baru tidak cocok!", "danger")
            return redirect(url_for("change_password"))

        # update password
        user.password = new_password
        db.session.commit()

        flash("Password berhasil diubah!", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth/change_password.html", user=user)

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username")

        user = User.query.filter_by(username=username).first()
        if not user:
            flash("Username tidak ditemukan!", "danger")
            return redirect(url_for("forgot_password"))

        # simpan id user sementara
        session["reset_user_id"] = user.id

        return redirect(url_for("reset_password"))

    return render_template("auth/forgot_password.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_user_id" not in session:
        return redirect(url_for("forgot_password"))

    user = User.query.get(session["reset_user_id"])

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Konfirmasi password tidak cocok!", "danger")
            return redirect(url_for("reset_password"))

        user.password = new_password
        db.session.commit()

        session.pop("reset_user_id", None)

        flash("Password berhasil direset! Silakan login.", "success")
        return redirect(url_for("login"))

    return render_template("auth/reset_password.html", user=user)


# Simple API for frontend stock check
@app.route('/api/products')
def api_products():
    items = Product.query.all()
    data = [{'id':p.id,'name':p.name,'price':p.price,'stock':p.stock} for p in items]
    return jsonify(data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    app.run(debug=True)