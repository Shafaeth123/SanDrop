import os
import re
import secrets
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app


features = Blueprint("features", __name__)

def _db():
    con = sqlite3.connect(os.path.join(current_app.root_path, "SanDrop.db"))
    con.row_factory = sqlite3.Row
    return con

def init_feature_db():
    con = _db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        token TEXT NOT NULL UNIQUE,
        subscribed INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        unsubscribed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS product_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        order_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        review TEXT NOT NULL,
        created_at TEXT NOT NULL,
        verified_purchase INTEGER NOT NULL DEFAULT 1,
        UNIQUE(product_id, order_id, customer_id),
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """)
    con.commit()
    con.close()

@features.app_context_processor
def feature_context():
    return {
        "wishlist_count": len(session.get("wishlist", [])),
        "recent_product_ids": session.get("recently_viewed", [])
    }

@features.route("/delivery")
def delivery_policy():
    return render_template("policy_delivery.html")

@features.route("/returns")
def returns_policy():
    return render_template("policy_returns.html")

@features.route("/size-guide")
def size_guide():
    return render_template("size_guide.html")

@features.route("/wishlist")
def wishlist_page():
    ids = []
    for raw in session.get("wishlist", []):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    products = []
    if ids:
        con = _db()
        marks = ",".join("?" for _ in ids)
        found = con.execute(
            f"SELECT * FROM products WHERE id IN ({marks}) AND available=1", ids
        ).fetchall()
        con.close()
        by_id = {p["id"]: p for p in found}
        products = [by_id[i] for i in ids if i in by_id]
    return render_template("wishlist.html", products=products)

@features.post("/wishlist/toggle")
def wishlist_toggle():
    try:
        pid = int(request.form.get("product_id", ""))
    except (TypeError, ValueError):
        flash("Invalid product.", "error")
        return redirect(request.referrer or url_for("shop"))
    con = _db()
    p = con.execute("SELECT id, available FROM products WHERE id=?", (pid,)).fetchone()
    con.close()
    if not p or not p["available"]:
        flash("Product is unavailable.", "error")
        return redirect(request.referrer or url_for("shop"))
    ids = []
    for raw in session.get("wishlist", []):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            pass
    if pid in ids:
        ids.remove(pid)
        flash("Removed from wishlist.", "success")
    else:
        ids.insert(0, pid)
        flash("Added to wishlist.", "success")
    session["wishlist"] = ids[:100]
    session.modified = True
    return redirect(request.referrer or url_for("wishlist"))

@features.post("/newsletter/subscribe")
def newsletter_subscribe():
    email = request.form.get("email", "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        flash("Enter a valid email address.", "error")
        return redirect(request.referrer or url_for("home"))
    token = secrets.token_urlsafe(32)
    con = _db()
    try:
        old = con.execute(
            "SELECT id, token, subscribed FROM newsletter_subscribers WHERE email=?",
            (email,)
        ).fetchone()
        if old:
            if old["subscribed"]:
                flash("This email is already subscribed.", "success")
            else:
                con.execute(
                    """UPDATE newsletter_subscribers
                       SET token=?, subscribed=1, created_at=?, unsubscribed_at=NULL
                       WHERE id=?""",
                    (token, datetime.now().isoformat(), old["id"])
                )
                flash("You are subscribed again.", "success")
        else:
            con.execute(
                """INSERT INTO newsletter_subscribers(email, token, subscribed, created_at)
                   VALUES(?,?,1,?)""",
                (email, token, datetime.now().isoformat())
            )
            flash("Thanks for subscribing!", "success")
        con.commit()
    except sqlite3.Error:
        con.rollback()
        current_app.logger.exception("Newsletter subscription failed")
        flash("Could not save your subscription. Please try again.", "error")
    finally:
        con.close()
    return redirect(request.referrer or url_for("home"))

@features.route("/newsletter/unsubscribe/<token>", methods=["GET", "POST"])
def newsletter_unsubscribe(token):
    con = _db()
    subscriber = con.execute(
        "SELECT id, email, subscribed FROM newsletter_subscribers WHERE token=?",
        (token,)
    ).fetchone()
    if not subscriber:
        con.close()
        return render_template("newsletter_unsubscribe.html", status="invalid", email=None)
    if request.method == "POST":
        con.execute(
            "UPDATE newsletter_subscribers SET subscribed=0, unsubscribed_at=? WHERE id=?",
            (datetime.now().isoformat(), subscriber["id"])
        )
        con.commit()
        con.close()
        return render_template("newsletter_unsubscribe.html", status="done", email=subscriber["email"])
    con.close()
    return render_template("newsletter_unsubscribe.html", status="confirm", email=subscriber["email"], token=token)

@features.route("/order-lookup", methods=["GET", "POST"])
def order_lookup():
    orders = []
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        order_id_text = request.form.get("order_id", "").strip()
        con = _db()
        if order_id_text:
            try:
                order_id = int(order_id_text)
            except ValueError:
                order_id = -1
            rows = con.execute("""
                SELECT o.*, c.name, c.email
                FROM orders o JOIN customers c ON c.id=o.customer_id
                WHERE o.id=? AND lower(c.email)=?
                ORDER BY o.id DESC
            """, (order_id, email)).fetchall()
        else:
            rows = con.execute("""
                SELECT o.*, c.name, c.email
                FROM orders o JOIN customers c ON c.id=o.customer_id
                WHERE lower(c.email)=?
                ORDER BY o.id DESC LIMIT 30
            """, (email,)).fetchall()
        orders = rows
        con.close()
        if not orders:
            flash("No matching orders were found. Check the email and order number.", "error")
    return render_template("order_lookup.html", orders=orders, email=email)

@features.route("/reviews/submit", methods=["POST"])
def submit_review():
    try:
        product_id = int(request.form.get("product_id", ""))
        order_id = int(request.form.get("order_id", ""))
        rating = int(request.form.get("rating", ""))
    except (TypeError, ValueError):
        flash("Please provide a valid product, order, and rating.", "error")
        return redirect(request.referrer or url_for("shop"))
    email = request.form.get("email", "").strip().lower()
    review = request.form.get("review", "").strip()
    if rating < 1 or rating > 5 or not review or len(review) > 2000:
        flash("Choose a rating and write a review of up to 2,000 characters.", "error")
        return redirect(url_for("product", pid=product_id))
    con = _db()
    try:
        purchase = con.execute("""
            SELECT o.id, o.customer_id
            FROM orders o
            JOIN customers c ON c.id=o.customer_id
            JOIN order_items oi ON oi.order_id=o.id
            WHERE o.id=? AND oi.product_id=? AND lower(c.email)=?
        """, (order_id, product_id, email)).fetchone()
        if not purchase:
            flash("A matching purchase could not be verified. Use the email from your order.", "error")
            return redirect(url_for("product", pid=product_id))
        con.execute("""
            INSERT INTO product_reviews
              (product_id, customer_id, order_id, rating, review, created_at, verified_purchase)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (product_id, purchase["customer_id"], order_id, rating, review, datetime.now().isoformat()))
        con.commit()
        flash("Thanks! Your verified-purchase review has been submitted.", "success")
    except sqlite3.IntegrityError:
        con.rollback()
        flash("A review for this product and order has already been submitted.", "error")
    except sqlite3.Error:
        con.rollback()
        current_app.logger.exception("Review submission failed")
        flash("Could not submit the review. Please try again.", "error")
    finally:
        con.close()
    return redirect(url_for("product", pid=product_id))



@features.route("/admin/reviews")
def admin_reviews():
    if session.get("admin") is not True:
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    rating = request.args.get("rating", "").strip()
    verified = request.args.get("verified", "").strip()

    con = _db()

    query = """
        SELECT
            r.id,
            r.product_id,
            r.customer_id,
            r.order_id,
            r.rating,
            r.review,
            r.created_at,
            r.verified_purchase,
            p.name AS product_name,
            p.image AS product_image,
            c.name AS customer_name,
            c.email AS customer_email,
            c.phone AS customer_phone,
            o.status AS order_status
        FROM product_reviews r
        LEFT JOIN products p ON p.id = r.product_id
        LEFT JOIN customers c ON c.id = r.customer_id
        LEFT JOIN orders o ON o.id = r.order_id
        WHERE 1=1
    """

    params = []

    if search:
        query += """
            AND (
                c.name LIKE ?
                OR c.email LIKE ?
                OR p.name LIKE ?
                OR r.review LIKE ?
            )
        """
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if rating in ("1", "2", "3", "4", "5"):
        query += " AND r.rating = ?"
        params.append(int(rating))

    if verified == "yes":
        query += " AND r.verified_purchase = 1"
    elif verified == "no":
        query += " AND r.verified_purchase = 0"

    query += " ORDER BY r.created_at DESC"

    reviews = con.execute(query, params).fetchall()

    review_analytics = con.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(ROUND(AVG(rating), 1), 0) AS average,
            COALESCE(SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END), 0) AS five_star,
            COALESCE(SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END), 0) AS one_star,
            COALESCE(SUM(CASE WHEN verified_purchase = 1 THEN 1 ELSE 0 END), 0) AS verified
        FROM product_reviews
    """).fetchone()

    con.close()

    return render_template(
        "admin_reviews.html",
        reviews=reviews,
        review_analytics=review_analytics,
        search=search,
        rating=rating,
        verified=verified
    )

@features.post("/admin/reviews/<int:review_id>/delete")
def admin_review_delete(review_id):
    if session.get("admin") is not True:
        return redirect(url_for("admin_login"))

    con = _db()

    try:
        con.execute(
            "DELETE FROM product_reviews WHERE id = ?",
            (review_id,)
        )
        con.commit()
    finally:
        con.close()

    flash("Review deleted successfully.", "success")
    return redirect(url_for("features.admin_reviews"))


