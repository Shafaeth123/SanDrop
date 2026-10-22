from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, secrets
from datetime import datetime, timedelta
from features import features, init_feature_db

import csv
import io


BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "SanDrop.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SanDrop_SECRET")

if not app.secret_key:
    raise RuntimeError(
        "SanDrop_SECRET is missing. Configure it before starting SanDrop."
    )

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SANDROP_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
)

UPLOAD_FOLDER = os.path.join(BASE, "static", "uploads", "products")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

SLIDES_UPLOAD_FOLDER = os.path.join(
    BASE, "static", "uploads", "slides"
)

os.makedirs(SLIDES_UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

CATEGORIES = ["T-Shirts", "Shirts", "Hoodies", "Dresses", "Pants", "Jackets"]

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        old_price REAL,
        description TEXT NOT NULL,
        image TEXT NOT NULL,
        sizes TEXT NOT NULL DEFAULT 'S,M,L,XL',
        colors TEXT NOT NULL DEFAULT 'Black,White',
        stock INTEGER NOT NULL DEFAULT 0,
        available INTEGER NOT NULL DEFAULT 1,
        featured INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS hero_slides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image TEXT NOT NULL,
    alt_text TEXT NOT NULL DEFAULT 'SanDrop Collection',
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
    );   

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        total REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'cod',
        transaction_id TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
         size TEXT,
         color TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    # Add payment_method if the existing database does not have it
    try:
        con.execute(
            "ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'cod'"
        )
    except sqlite3.OperationalError:
        pass

    # Add additional product images to existing databases
    try:
        con.execute(
            "ALTER TABLE products ADD COLUMN images TEXT NOT NULL DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    
    # Add cost price for profit analytics
    try:
      con.execute(
        "ALTER TABLE products ADD COLUMN cost_price REAL NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
     pass

    # Add transaction_id if the existing database does not have it
    try:
        con.execute(
            "ALTER TABLE orders ADD COLUMN transaction_id TEXT"
        )
    except sqlite3.OperationalError:
        pass
 # Add size if the existing order_items table does not have it
    try:
     con.execute(
        "ALTER TABLE order_items ADD COLUMN size TEXT"
    )
    except sqlite3.OperationalError:
     pass

 # Add color if the existing order_items table does not have it
 
    try:
     con.execute(
        "ALTER TABLE order_items ADD COLUMN color TEXT"
     )
    except sqlite3.OperationalError:
     pass
# Add cost_price to order_items for profit analytics
    try:
       con.execute(
        "ALTER TABLE order_items ADD COLUMN cost_price REAL NOT NULL DEFAULT 0"
      )
    except sqlite3.OperationalError:
     pass


    
    # Create default admin
    if con.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO admins(username,password) VALUES(?,?)",
            ("admin", generate_password_hash("SanDrop123"))
        )
        
        

    # Add demo products only if there are no products
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:

        now = datetime.now().isoformat()

        demo = [
            (
                "Essential Oversized Tee",
                "T-Shirts",
                1290,
                1590,
                "A premium heavyweight oversized T-shirt with a clean silhouette and everyday comfort.",
                "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL,XXL",
                "Black,White,Navy",
                42,
                1,
                1
            ),

            (
                "Studio White Shirt",
                "Shirts",
                1890,
                2290,
                "Minimal cotton shirt designed for smart casual styling.",
                "https://images.unsplash.com/photo-1603252110481-7ba873bf42ab?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL",
                "White,Beige",
                26,
                1,
                1
            ),

            (
                "Noir Essential Hoodie",
                "Hoodies",
                2490,
                2990,
                "Soft premium hoodie with a structured fit and understated branding.",
                "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL,XXL",
                "Black,Grey",
                18,
                1,
                1
            ),

            (
                "Modern Pleated Pants",
                "Pants",
                2190,
                2590,
                "Relaxed pleated trousers with a polished modern finish.",
                "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL",
                "Black,Charcoal",
                31,
                1,
                0
            ),

            (
                "Silk Evening Dress",
                "Dresses",
                3490,
                3990,
                "Elegant flowing dress made for evening occasions and refined styling.",
                "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL",
                "Black,Burgundy",
                12,
                1,
                1
            ),

            (
                "Urban Denim Jacket",
                "Jackets",
                2890,
                3290,
                "Classic denim jacket with a contemporary streetwear profile.",
                "https://images.unsplash.com/photo-1551537482-f2075a1d41f2?auto=format&fit=crop&w=1000&q=85",
                "S,M,L,XL",
                "Blue,Black",
                20,
                1,
                0
            )
        ]

        con.executemany(
            """
            INSERT INTO products
            (
                name,
                category,
                price,
                old_price,
                description,
                image,
                sizes,
                colors,
                stock,
                available,
                featured,
                created_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [x + (now,) for x in demo]
        )

    con.commit()
    con.close()
def cart_data():
    cart = session.get("cart", {})

    if not cart:
        return [], 0

    # Convert old cart format if needed
    normalized_cart = {}

    for key, qty in cart.items():

        # Old cart format: {"1": 2}
        if "|" not in str(key):
            normalized_cart[f"{key}|||"] = int(qty)

        # New cart format:
        # {"1|XL|Black": 2}
        else:
            normalized_cart[str(key)] = int(qty)

    session["cart"] = normalized_cart

    product_ids = []

    for key in normalized_cart:
        product_id = int(str(key).split("|")[0])
        product_ids.append(product_id)

    product_ids = list(set(product_ids))

    if not product_ids:
        return [], 0

    placeholders = ",".join("?" for _ in product_ids)

    con = db()

    products = con.execute(
        f"""
        SELECT *
        FROM products
        WHERE id IN ({placeholders})
        """,
        product_ids
    ).fetchall()

    con.close()

    product_map = {
        p["id"]: p
        for p in products
    }

    items = []
    total = 0

    for key, qty in normalized_cart.items():

        parts = str(key).split("|")

        product_id = int(parts[0])

        size = parts[1] if len(parts) > 1 and parts[1] else ""
        color = parts[2] if len(parts) > 2 and parts[2] else ""

        product = product_map.get(product_id)

        if not product:
            continue

        qty = int(qty)

        if qty <= 0:
            continue

        subtotal = product["price"] * qty

        total += subtotal

        items.append({
            "product": product,
            "qty": qty,
            "size": size,
            "color": color,
            "subtotal": subtotal,
            "cart_key": key
        })

    return items, total

@app.context_processor
def inject():
    items, total = cart_data()
    return {
    "cart_count": sum(i["qty"] for i in items),
    "cart_total": total,
    "categories": CATEGORIES,
    "wishlist_count": len(session.get("wishlist", []))
       }

@app.context_processor
def admin_notification_data():
    if session.get("admin") is not True:
      return {}

    try:
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row

        pending_count = con.execute("""
            SELECT COUNT(*) FROM orders
            WHERE status = 'Pending'
        """).fetchone()[0]

        low_stock_count = con.execute("""
            SELECT COUNT(*) FROM products
            WHERE stock <= 5 AND available = 1
        """).fetchone()[0]

        notifications = con.execute("""
            SELECT id, total, status, created_at
            FROM orders
            WHERE status = 'Pending'
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall()

        con.close()

        return {
            "admin_pending_count": pending_count,
            "admin_low_stock_count": low_stock_count,
            "admin_notifications": notifications
        }

    except sqlite3.Error:
        return {
            "admin_pending_count": 0,
            "admin_low_stock_count": 0,
            "admin_notifications": []
        }

@app.route("/")
def home():
    con = db()

    try:
        featured = con.execute("""
            SELECT * FROM products
            WHERE featured=1 AND available=1
            ORDER BY id DESC LIMIT 6
        """).fetchall()

        latest = con.execute("""
            SELECT * FROM products
            WHERE available=1
            ORDER BY id DESC LIMIT 8
        """).fetchall()

        slides = con.execute("""
            SELECT image, alt_text
            FROM hero_slides
            WHERE active=1
            ORDER BY sort_order ASC, id DESC
        """).fetchall()

        hero_slides = [
            {
                "url": url_for("static", filename=slide["image"]),
                "alt": slide["alt_text"]
            }
            for slide in slides
        ]

    finally:
        con.close()

    if not hero_slides:
        hero_slides = [{
            "url": url_for("static", filename="images/lol.jpg"),
            "alt": "SanDrop Men's Collection"
        }]

    return render_template(
        "index.html",
        featured=featured,
        latest=latest,
        hero_slides=hero_slides
    )


@app.route("/shop")
def shop():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    size = request.args.get("size", "").strip()
    color = request.args.get("color", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort = request.args.get("sort", "newest")

    # Validate price filters
    try:
        min_value = float(min_price) if min_price else None
        max_value = float(max_price) if max_price else None

        if (
            (min_value is not None and min_value < 0)
            or (max_value is not None and max_value < 0)
            or (min_value is not None and not __import__("math").isfinite(min_value))
            or (max_value is not None and not __import__("math").isfinite(max_value))
        ):
            raise ValueError

        if (
            min_value is not None
            and max_value is not None
            and min_value > max_value
        ):
            flash("Minimum price cannot exceed maximum price.", "error")
            return redirect(url_for("shop"))

    except ValueError:
        flash("Please enter valid, non-negative prices.", "error")
        return redirect(url_for("shop"))

    con = db()

    # Build filter options from actual products
    all_options = con.execute("""
        SELECT sizes, colors
        FROM products
        WHERE available = 1
    """).fetchall()

    available_sizes = set()
    available_colors = set()

    for row in all_options:
        available_sizes.update(
            x.strip() for x in (row["sizes"] or "").split(",") if x.strip()
        )
        available_colors.update(
            x.strip() for x in (row["colors"] or "").split(",") if x.strip()
        )

    size_order = ["XS", "S", "M", "L", "XL", "XXL"]
    available_sizes = sorted(
        available_sizes,
        key=lambda x: (
            size_order.index(x) if x in size_order else len(size_order),
            x
        )
    )
    available_colors = sorted(available_colors)

    sql = "SELECT * FROM products WHERE available = 1"
    params = []

    if q:
        sql += " AND (name LIKE ? OR category LIKE ? OR description LIKE ?)"
        params.extend([f"%{q}%"] * 3)

    if category:
        sql += " AND category = ?"
        params.append(category)

    if size:
        sql += " AND (',' || sizes || ',') LIKE ?"
        params.append(f"%,{size},%")

    if color:
        sql += " AND (',' || colors || ',') LIKE ?"
        params.append(f"%,{color},%")

    if min_value is not None:
        sql += " AND price >= ?"
        params.append(min_value)

    if max_value is not None:
        sql += " AND price <= ?"
        params.append(max_value)

    if sort == "low":
        sql += " ORDER BY price ASC"
    elif sort == "high":
        sql += " ORDER BY price DESC"
    elif sort == "name":
        sql += " ORDER BY name ASC"
    else:
        sql += " ORDER BY id DESC"

    products = con.execute(sql, params).fetchall()
    con.close()

    return render_template(
        "shop.html",
        products=products,
        q=q,
        category=category,
        sort=sort,
        size=size,
        color=color,
        min_price=min_price,
        max_price=max_price,
        available_sizes=available_sizes,
        available_colors=available_colors
    )

@app.route("/product/<int:pid>")
def product(pid):
    con = db()

    p = con.execute(
        "SELECT * FROM products WHERE id = ?",
        (pid,)
    ).fetchone()

    related = con.execute(
        """
        SELECT * FROM products
        WHERE category = ? AND id != ? AND available = 1
        LIMIT 4
        """,
        (p["category"], pid)
    ).fetchall() if p else []

    con.close()

    if not p:
        return "Product not found", 404
    recent = session.get("recently_viewed", [])
    recent = [int(x) for x in recent if str(x).isdigit() and int(x) != pid]
    recent.insert(0, pid)
    session["recently_viewed"] = recent[:8]
    session.modified = True
    # Convert the saved image string into a Python list
    p_images = [
        img.strip()
        for img in (p["images"] or "").split("|")
        if img.strip()
    ]
    
    con = db()
    reviews = con.execute("""
    SELECT rating, review, created_at, verified_purchase
    FROM product_reviews
    WHERE product_id = ?
    ORDER BY created_at DESC
     """, (pid,)).fetchall()

    review_stats = con.execute("""
    SELECT COUNT(*) AS total, AVG(rating) AS average
    FROM product_reviews
    WHERE product_id = ?
     """, (pid,)).fetchone()

    con.close()
     
    return render_template(
        "product.html",
        p=p,
        related=related,
        p_images=p_images,
        reviews=reviews,
    review_stats=review_stats
    )



@app.post("/cart/add")
def add_cart():
    raw_pid = request.form.get("product_id") or request.args.get("product_id")

    try:
        pid = int(raw_pid)
        qty = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        flash("Invalid product or quantity.", "error")
        return redirect(url_for("shop"))

    if qty < 1:
        flash("Quantity must be at least 1.", "error")
        return redirect(url_for("shop"))

    size = request.form.get("size", "").strip()
    color = request.form.get("color", "").strip()

    con = db()
    product = con.execute(
        "SELECT * FROM products WHERE id = ? AND available = 1",
        (pid,)
    ).fetchone()
    con.close()

    if not product:
        flash("Product not found or unavailable.", "error")
        return redirect(url_for("shop"))

    if product["stock"] < 1:
        flash("This product is out of stock.", "error")
        return redirect(url_for("product", pid=pid))

    if qty > product["stock"]:
        flash("Requested quantity exceeds available stock.", "error")
        return redirect(url_for("product", pid=pid))

    available_sizes = [
        value.strip() for value in (product["sizes"] or "").split(",")
        if value.strip()
    ]
    available_colors = [
        value.strip() for value in (product["colors"] or "").split(",")
        if value.strip()
    ]

    if available_sizes and size not in available_sizes:
        flash("Please select a valid size.", "error")
        return redirect(url_for("product", pid=pid))

    if available_colors and color not in available_colors:
        flash("Please select a valid color.", "error")
        return redirect(url_for("product", pid=pid))

    cart = session.get("cart", {})
    cart_key = f"{pid}|{size}|{color}"
    new_qty = int(cart.get(cart_key, 0)) + qty

    if new_qty > product["stock"]:
        flash("Your cart quantity would exceed available stock.", "error")
        return redirect(url_for("product", pid=pid))

    cart[cart_key] = new_qty
    session["cart"] = cart
    session.modified = True

    flash("Product added to your bag successfully!", "success")
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    items, total = cart_data()
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/update")
def update_cart():

    cart_key = request.form["cart_key"]

    qty = max(
        0,
        int(request.form["quantity"])
    )

    parts = cart_key.split("|")

    pid = int(parts[0])

    con = db()

    p = con.execute(
        "SELECT stock FROM products WHERE id=?",
        (pid,)
    ).fetchone()

    con.close()

    cart = session.get("cart", {})

    if qty == 0:

        cart.pop(cart_key, None)

    elif p and qty <= p["stock"]:

        cart[cart_key] = qty

    else:

        flash(
            "Requested quantity exceeds available stock.",
            "error"
        )

    session["cart"] = cart

    return redirect(url_for("cart"))

@app.post("/cart/remove")
def remove_cart():
    cart = session.get("cart", {})

    cart_key = request.form.get("cart_key", "")

    cart.pop(cart_key, None)

    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, total = cart_data()

    if not items:
        flash("Your bag is empty.", "error")
        return redirect(url_for("cart"))

    if request.method == "GET":
        return render_template(
            "checkout.html",
            items=items,
            total=total
        )

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    payment_method = request.form.get(
        "payment_method", "cod"
    ).strip().lower()

    if not all([name, email, phone, address]):
        flash("Please complete all customer fields.", "error")
        return render_template(
            "checkout.html", items=items, total=total
        ), 400

    if payment_method not in ("cod", "bkash", "nagad"):
        flash("Invalid payment method.", "error")
        return render_template(
            "checkout.html", items=items, total=total
        ), 400

    if payment_method == "bkash":
        transaction_id = request.form.get(
            "bkash_transaction_id", ""
        ).strip()
    elif payment_method == "nagad":
        transaction_id = request.form.get(
            "nagad_transaction_id", ""
        ).strip()
    else:
        transaction_id = None

    if payment_method in ("bkash", "nagad") and not transaction_id:
        flash(
            f"Please enter your {payment_method.title()} Transaction ID.",
            "error"
        )
        return render_template(
            "checkout.html", items=items, total=total
        ), 400

    con = db()

    try:
        # Verify stock again before creating the order.
        for item in items:
            product = con.execute(
                "SELECT stock, available FROM products WHERE id = ?",
                (item["product"]["id"],)
            ).fetchone()

            if (
                not product
                or not product["available"]
                or item["qty"] > product["stock"]
            ):
                con.rollback()
                flash(
                    f"Insufficient stock for {item['product']['name']}.",
                    "error"
                )
                return redirect(url_for("cart"))

        now = datetime.now().isoformat()

        cursor = con.execute(
            """
            INSERT INTO customers (name, email, phone, address, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, phone, address, now)
        )
        customer_id = cursor.lastrowid

        cursor = con.execute(
            """
            INSERT INTO orders
                (customer_id, total, payment_method, transaction_id,
                 status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id, total, payment_method,
                transaction_id, "Pending", now
            )
        )
        order_id = cursor.lastrowid

        for item in items:
            pid = item["product"]["id"]
            qty = item["qty"]

            con.execute(
                """
                INSERT INTO order_items
                    (order_id, product_id, quantity, price, cost_price, size, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    pid,
                    qty,
                    item["product"]["price"],
                    item["product"]["cost_price"],
                    item["size"],
                    item["color"]
                )
            )


            con.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (qty, pid)
            )

        con.commit()

    except sqlite3.Error:
        con.rollback()
        app.logger.exception("Checkout database error")
        flash("Could not place your order. Please try again.", "error")
        return redirect(url_for("checkout"))

    finally:
        con.close()

    session["cart"] = {}
    flash(f"Order #{order_id} placed successfully!", "success")
    return redirect(url_for("home"))


# ---------------- ADMIN ----------------
def admin_required():
    return session.get("admin") is True


@app.route("/admin/hero-slides", methods=["GET", "POST"])
def admin_hero_slides():
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()

    try:
        if request.method == "POST":
            files = [
                f for f in request.files.getlist("images")
                if f and f.filename
            ]

            alt_text = (
                request.form.get("alt_text", "SanDrop Collection").strip()
                or "SanDrop Collection"
            )

            if not files:
                flash("Please select at least one image.", "error")
                return redirect(url_for("admin_hero_slides"))

            if len(files) > 10:
                flash("Upload a maximum of 10 images at a time.", "error")
                return redirect(url_for("admin_hero_slides"))

            if any(not allowed_file(f.filename) for f in files):
                flash("Only JPG, JPEG, PNG and WEBP images are allowed.", "error")
                return redirect(url_for("admin_hero_slides"))

            saved_files = []

            try:
                for file in files:
                    filename = secure_filename(file.filename)
                    unique_name = f"{secrets.token_hex(12)}_{filename}"
                    path = os.path.join(SLIDES_UPLOAD_FOLDER, unique_name)

                    file.save(path)
                    saved_files.append(path)

                    con.execute("""
                        INSERT INTO hero_slides
                            (image, alt_text, active, sort_order, created_at)
                        VALUES (?, ?, 1, 0, ?)
                    """, (
                        f"uploads/slides/{unique_name}",
                        alt_text[:150],
                        datetime.now().isoformat()
                    ))

                con.commit()

            except Exception:
                con.rollback()

                for path in saved_files:
                    if os.path.isfile(path):
                        os.remove(path)

                app.logger.exception("Hero slide upload failed")
                flash("Could not upload images. Please try again.", "error")
                return redirect(url_for("admin_hero_slides"))

            flash("Slideshow images uploaded successfully.", "success")
            return redirect(url_for("admin_hero_slides"))

        slides = con.execute("""
            SELECT * FROM hero_slides
            ORDER BY id DESC
        """).fetchall()

        return render_template("admin_hero_slides.html", slides=slides)

    finally:
        con.close()


@app.post("/admin/hero-slides/<int:slide_id>/toggle")
def admin_hero_slide_toggle(slide_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()
    try:
        con.execute("""
            UPDATE hero_slides
            SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, (slide_id,))
        con.commit()
    finally:
        con.close()

    flash("Slideshow image status updated.", "success")
    return redirect(url_for("admin_hero_slides"))


@app.post("/admin/hero-slides/<int:slide_id>/delete")
def admin_hero_slide_delete(slide_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()
    try:
        slide = con.execute(
            "SELECT image FROM hero_slides WHERE id = ?",
            (slide_id,)
        ).fetchone()

        if not slide:
            flash("Slideshow image not found.", "error")
            return redirect(url_for("admin_hero_slides"))

        con.execute(
            "DELETE FROM hero_slides WHERE id = ?",
            (slide_id,)
        )
        con.commit()

        image = slide["image"]

        if image.startswith("uploads/slides/"):
            filename = os.path.basename(image)
            path = os.path.abspath(
                os.path.join(SLIDES_UPLOAD_FOLDER, filename)
            )

            if (
                os.path.dirname(path) == os.path.abspath(SLIDES_UPLOAD_FOLDER)
                and os.path.isfile(path)
            ):
                try:
                    os.remove(path)
                except OSError:
                    app.logger.exception("Could not delete slideshow image")

    finally:
        con.close()

    flash("Slideshow image deleted.", "success")
    return redirect(url_for("admin_hero_slides"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin") is True:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        con = db()
        try:
            admin = con.execute(
                "SELECT * FROM admins WHERE username = ?",
                (username,)
            ).fetchone()
        finally:
            con.close()

        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    from datetime import timedelta

    con = db()
    today = datetime.now().date()

    period = request.args.get("period", "7days")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    if period == "today":
        date_from = today.isoformat()
        date_to = today.isoformat()
    elif period == "7days":
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()
    elif period == "30days":
        date_from = (today - timedelta(days=29)).isoformat()
        date_to = today.isoformat()
    elif period == "all":
        date_from = ""
        date_to = ""
    elif period != "custom":
        period = "7days"
        date_from = (today - timedelta(days=6)).isoformat()
        date_to = today.isoformat()

    stats = {
        "products": con.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0],
        "customers": con.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0],
        "orders": con.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0],
        "revenue": 0,
        "low_stock": con.execute(
            "SELECT COUNT(*) FROM products WHERE stock <= 5"
        ).fetchone()[0]
    }

    date_conditions = ""
    date_params = []

    if date_from:
        date_conditions += " AND date(o.created_at) >= date(?)"
        date_params.append(date_from)

    if date_to:
        date_conditions += " AND date(o.created_at) <= date(?)"
        date_params.append(date_to)

    stats["revenue"] = con.execute(
        """
        SELECT COALESCE(SUM(o.total), 0)
        FROM orders o
        WHERE o.status != 'Cancelled'
        """ + date_conditions,
        date_params
    ).fetchone()[0]

    # Order status analytics
    status_rows = con.execute("""
        SELECT status, COUNT(*) AS total
        FROM orders
        GROUP BY status
    """).fetchall()

    order_status = {
        "Pending": 0,
        "Confirmed": 0,
        "Processing": 0,
        "Shipped": 0,
        "Delivered": 0,
        "Cancelled": 0
    }

    for row in status_rows:
        order_status[row["status"]] = row["total"]

    # Last 7 days sales chart
    sales_chart = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        revenue = con.execute("""
            SELECT COALESCE(SUM(total), 0)
            FROM orders
            WHERE date(created_at) = ?
              AND status != 'Cancelled'
        """, (day.isoformat(),)).fetchone()[0]

        sales_chart.append({
            "date": day.strftime("%b %d"),
            "revenue": revenue
        })

    # Low-stock products
    low_stock_products = con.execute("""
        SELECT id, name, stock
        FROM products
        WHERE stock <= 5
        ORDER BY stock ASC, name ASC
        LIMIT 8
    """).fetchall()

    # Top-selling products for selected date range
    top_products = con.execute("""
        SELECT
            p.id,
            p.name,
            COALESCE(SUM(oi.quantity), 0) AS units_sold,
            COALESCE(SUM(oi.quantity * oi.price), 0) AS sales
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status != 'Cancelled'
    """ + date_conditions + """
        GROUP BY p.id, p.name
        ORDER BY units_sold DESC, sales DESC
        LIMIT 5
    """, date_params).fetchall()
  
    # Profit analytics for selected date range
    profit_stats = con.execute("""
        SELECT
            COALESCE(SUM(oi.quantity * oi.price), 0) AS sales,
            COALESCE(SUM(oi.quantity * oi.cost_price), 0) AS cost,
            COALESCE(
                SUM(oi.quantity * (oi.price - oi.cost_price)), 0
            ) AS profit
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status != 'Cancelled'
    """ + date_conditions, date_params).fetchone()

    # Recent orders
    recent = con.execute("""
        SELECT o.*, c.name
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        ORDER BY o.id DESC
        LIMIT 8
    """).fetchall()

    # Admin notifications
    new_orders_count = con.execute("""
        SELECT COUNT(*)
        FROM orders
        WHERE status = 'Pending'
    """).fetchone()[0]

    low_stock_count = con.execute("""
        SELECT COUNT(*)
        FROM products
        WHERE stock <= 5 AND available = 1
    """).fetchone()[0]

    recent_notifications = con.execute("""
        SELECT id, total, status, created_at
        FROM orders
        WHERE status = 'Pending'
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()

    con.close()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        recent=recent,
            new_orders_count=new_orders_count,
    low_stock_count=low_stock_count,
    recent_notifications=recent_notifications,
        profit_stats=profit_stats,
        order_status=order_status,
        sales_chart=sales_chart,
        low_stock_products=low_stock_products,
        top_products=top_products,
        period=period,
        date_from=date_from,
        date_to=date_to
    )


@app.route("/admin/products")
def admin_products():
    if not admin_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    stock_status = request.args.get("stock", "").strip()
    availability = request.args.get("availability", "").strip()

    con = db()

    sql = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        sql += " AND (name LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])

    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    if stock_status == "out":
        sql += " AND stock = 0"
    elif stock_status == "low":
        sql += " AND stock > 0 AND stock <= 5"
    elif stock_status == "in":
        sql += " AND stock > 5"

    if availability == "available":
        sql += " AND available = 1"
    elif availability == "unavailable":
        sql += " AND available = 0"

    sql += " ORDER BY id DESC"

    products = con.execute(sql, params).fetchall()
    con.close()

    return render_template(
        "admin_products.html",
        products=products,
        categories=CATEGORIES,
        search=search,
        category=category,
        stock_status=stock_status,
        availability=availability
    )



@app.route("/admin/products/new", methods=["GET", "POST"])
@app.route("/admin/products/<int:pid>/edit", methods=["GET", "POST"])
def admin_product_form(pid=None):
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()

    try:
        p = None

        if pid is not None:
            p = con.execute(
                "SELECT * FROM products WHERE id = ?",
                (pid,)
            ).fetchone()

            if not p:
                return "Product not found", 404

        if request.method == "POST":

            # Read existing image information
            main_image = p["image"] if p else ""
            existing_images = []

            if p and p["images"]:
                existing_images = [
                    img.strip()
                    for img in p["images"].split("|")
                    if img.strip()
                ]

            # Check selected additional images for deletion
            remove_images = set(request.form.getlist("remove_images"))

            # Only allow deletion of images already associated
            # with this product.
            valid_removed_images = [
                img for img in existing_images
                if img in remove_images
            ]

            remaining_images = [
                img for img in existing_images
                if img not in remove_images
            ]

            # Upload main image, if a replacement is provided
            image_file = request.files.get("image")
            new_main_image = None

            if image_file and image_file.filename:
                if not allowed_file(image_file.filename):
                    flash(
                        "Only JPG, JPEG, PNG and WEBP images are allowed.",
                        "error"
                    )
                    return redirect(request.url)

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                filename = secure_filename(image_file.filename)
                unique_name = f"{secrets.token_hex(8)}_{filename}"
                image_file.save(
                    os.path.join(UPLOAD_FOLDER, unique_name)
                )

                new_main_image = f"uploads/products/{unique_name}"
                main_image = new_main_image

            # Upload new additional images
            new_images = []

            for file in request.files.getlist("additional_images"):
                if not file or not file.filename:
                    continue

                if not allowed_file(file.filename):
                    flash(
                        "Only JPG, JPEG, PNG and WEBP images are allowed.",
                        "error"
                    )
                    return redirect(request.url)

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                filename = secure_filename(file.filename)
                unique_name = f"{secrets.token_hex(8)}_{filename}"

                file.save(os.path.join(UPLOAD_FOLDER, unique_name))

                new_images.append(
                    f"uploads/products/{unique_name}"
                )

            # Keep remaining images and append newly uploaded ones
            all_images = remaining_images + new_images
            images_value = "|".join(all_images)

            # Product fields
            name = request.form["name"].strip()
            category = request.form["category"].strip()
            price = float(request.form["price"])
            cost_price = float(request.form.get("cost_price", 0))
            old_price_text = request.form.get("old_price", "").strip()
            old_price = float(old_price_text) if old_price_text else None
            description = request.form["description"].strip()
            sizes = request.form.get("sizes", "S,M,L,XL").strip()
            colors = request.form.get("colors", "Black,White").strip()
            stock = int(request.form["stock"])
            available = 1 if request.form.get("available") else 0
            featured = 1 if request.form.get("featured") else 0

            if not name or not category or not description:
                flash("Please fill in all required fields.", "error")
                return redirect(request.url)

            if (
                price < 0
                or cost_price < 0
                or (old_price is not None and old_price < 0)
            ):
                flash("Prices cannot be negative.", "error")
                return redirect(request.url)

            if stock < 0:
                flash("Stock cannot be negative.", "error")
                return redirect(request.url)

            # Save product to database
            if p:
                con.execute(
                    """
                    UPDATE products
                    SET name = ?,
                        category = ?,
                        price = ?,
                        cost_price = ?,
                        old_price = ?,
                        description = ?,
                        image = ?,
                        images = ?,
                        sizes = ?,
                        colors = ?,
                        stock = ?,
                        available = ?,
                        featured = ?
                    WHERE id = ?
                    """,
                    (
                        name, category, price, cost_price, old_price,
                        description, main_image, images_value,
                        sizes, colors, stock, available, featured, pid
                    )
                )

            else:
                con.execute(
                    """
                    INSERT INTO products (
                        name, category, price, cost_price, old_price,
                        description, image, images, sizes, colors,
                        stock, available, featured, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name, category, price, cost_price, old_price,
                        description, main_image, images_value, sizes,
                        colors, stock, available, featured,
                        datetime.now().isoformat()
                    )
                )


            con.commit()

            # Delete physical files only after database commit.
            # Never delete files outside the product upload folder.
            for image in valid_removed_images:
                if image.startswith("uploads/products/"):
                    filename = os.path.basename(image)
                    file_path = os.path.abspath(
                        os.path.join(UPLOAD_FOLDER, filename)
                    )
                    upload_folder = os.path.abspath(UPLOAD_FOLDER)

                    if (
                        os.path.dirname(file_path) == upload_folder
                        and os.path.isfile(file_path)
                        and image != main_image
                    ):
                        try:
                            os.remove(file_path)
                        except OSError:
                            app.logger.exception(
                                "Could not delete product image: %s",
                                filename
                            )

            flash("Product saved successfully.", "success")
            return redirect(url_for("admin_products"))

        return render_template("admin_product_form.html", p=p)

    finally:
        con.close()



@app.post("/admin/products/<int:pid>/delete")
def admin_product_delete(pid):
    if not admin_required(): return redirect(url_for("admin_login"))
    con = db(); con.execute("DELETE FROM products WHERE id=?", (pid,)); con.commit(); con.close()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
def admin_orders():
    if not admin_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    valid_statuses = [
        "Pending", "Confirmed", "Processing",
        "Shipped", "Delivered", "Cancelled"
    ]

    con = db()

    sql = """
        SELECT o.*, c.name, c.email, c.phone, c.address
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE 1=1
    """
    params = []

    if search:
        term = f"%{search}%"
        sql += """
            AND (
                CAST(o.id AS TEXT) LIKE ?
                OR c.name LIKE ?
                OR c.email LIKE ?
                OR c.phone LIKE ?
                OR c.address LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM order_items oi
                    JOIN products p ON p.id = oi.product_id
                    WHERE oi.order_id = o.id
                    AND p.name LIKE ?
                )
            )
        """
        params.extend([term] * 6)

    if status in valid_statuses:
        sql += " AND o.status = ?"
        params.append(status)

    if date_from:
        sql += " AND date(o.created_at) >= date(?)"
        params.append(date_from)

    if date_to:
        sql += " AND date(o.created_at) <= date(?)"
        params.append(date_to)

    sql += " ORDER BY o.id DESC"

    orders = con.execute(sql, params).fetchall()

    order_items = con.execute("""
        SELECT oi.*, p.name AS product_name, p.image AS product_image
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        ORDER BY oi.order_id DESC, oi.id ASC
    """).fetchall()

    items_by_order = {}
    for item in order_items:
        order_id = item["order_id"]
        items_by_order.setdefault(order_id, []).append(item)

    con.close()

    return render_template(
        "admin_orders.html",
        orders=orders,
        items_by_order=items_by_order,
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to
    )


@app.post("/admin/orders/<int:oid>/status")
def admin_order_status(oid):
    if not admin_required(): return redirect(url_for("admin_login"))
    con=db(); con.execute("UPDATE orders SET status=? WHERE id=?",(request.form["status"],oid)); con.commit(); con.close()
    return redirect(url_for("admin_orders"))



@app.route("/admin/customers")
def admin_customers():
    if not admin_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    con = db()

    try:
        sql = """
            SELECT
                c.*,

                (
                    SELECT COUNT(o.id)
                    FROM orders o
                    JOIN customers cx ON cx.id = o.customer_id
                    WHERE LOWER(TRIM(cx.email)) =
                          LOWER(TRIM(c.email))
                ) AS total_orders,

                (
                    SELECT COALESCE(SUM(o.total), 0)
                    FROM orders o
                    JOIN customers cx ON cx.id = o.customer_id
                    WHERE LOWER(TRIM(cx.email)) =
                          LOWER(TRIM(c.email))
                      AND o.status != 'Cancelled'
                ) AS total_spending,

                (
                    SELECT MAX(o.created_at)
                    FROM orders o
                    JOIN customers cx ON cx.id = o.customer_id
                    WHERE LOWER(TRIM(cx.email)) =
                          LOWER(TRIM(c.email))
                ) AS last_order

            FROM customers c

            WHERE c.id = (
                SELECT MAX(c2.id)
                FROM customers c2
                WHERE LOWER(TRIM(c2.email)) =
                      LOWER(TRIM(c.email))
            )
        """

        params = []

        if search:
            term = f"%{search}%"
            sql += """
                AND (
                    c.name LIKE ?
                    OR c.email LIKE ?
                    OR c.phone LIKE ?
                    OR c.address LIKE ?
                    OR CAST(c.id AS TEXT) LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM customers cs
                        WHERE LOWER(TRIM(cs.email)) =
                              LOWER(TRIM(c.email))
                          AND (
                              cs.name LIKE ?
                              OR cs.phone LIKE ?
                              OR cs.address LIKE ?
                          )
                    )
                )
            """
            params.extend([term] * 8)

        sql += " ORDER BY c.id DESC"

        customers = con.execute(sql, params).fetchall()

    finally:
        con.close()

    return render_template(
        "admin_customers.html",
        customers=customers,
        search=search
    )

@app.route("/admin/customers/<int:customer_id>")
def admin_customer_detail(customer_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()

    try:
        # Find selected customer
        customer = con.execute("""
            SELECT *
            FROM customers
            WHERE id = ?
        """, (customer_id,)).fetchone()

        if not customer:
            return "Customer not found", 404

        # Include orders from customer records with the same email
        orders = con.execute("""
            SELECT o.*, c.name AS customer_name
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE LOWER(TRIM(c.email)) = LOWER(TRIM(?))
            ORDER BY o.created_at DESC, o.id DESC
        """, (customer["email"],)).fetchall()

        # Get products purchased in these orders
        order_items = con.execute("""
            SELECT
                oi.*,
                p.name AS product_name,
                p.image AS product_image
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN customers c ON c.id = o.customer_id
            JOIN products p ON p.id = oi.product_id
            WHERE LOWER(TRIM(c.email)) = LOWER(TRIM(?))
            ORDER BY o.id DESC, oi.id ASC
        """, (customer["email"],)).fetchall()

        items_by_order = {}

        for item in order_items:
            items_by_order.setdefault(
                item["order_id"], []
            ).append(item)

        total_orders = len(orders)

        total_spending = sum(
            order["total"]
            for order in orders
            if order["status"] != "Cancelled"
        )

    finally:
        con.close()

    return render_template(
        "admin_customer_detail.html",
        customer=customer,
        orders=orders,
        items_by_order=items_by_order,
        total_orders=total_orders,
        total_spending=total_spending
    )

@app.route("/admin/export/orders.csv")
def admin_export_orders():
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db()

    orders = con.execute("""
        SELECT
            o.id,
            o.created_at,
            o.customer_id,
            o.total,
            o.payment_method,
            o.transaction_id,
            o.status
        FROM orders o
        ORDER BY o.created_at DESC
    """).fetchall()

    con.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Order ID",
        "Date",
        "Customer ID",
        "Total",
        "Payment Method",
        "Transaction ID",
        "Status"
    ])

    for order in orders:
        writer.writerow([
            order["id"],
            order["created_at"],
            order["customer_id"],
            order["total"],
            order["payment_method"],
            order["transaction_id"],
            order["status"]
        ])

    from flask import Response

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=SanDrop_orders.csv"
        }
    )


if __name__ == "__main__":
    app.register_blueprint(features)

    with app.app_context():
        init_db()
        init_feature_db()

    app.run(host="0.0.0.0", port=5000, debug=False)