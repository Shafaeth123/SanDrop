# SORTAN — Premium Fashion Store

A complete Flask + SQLite clothing store with:
- Premium responsive storefront
- Product catalog, search and category filters
- Product detail pages
- Cart and checkout
- Customer order storage
- Admin dashboard
- Product CRUD
- Stock and availability management
- Automatic stock reduction after checkout
- SQLite database created automatically

## Windows setup

```bat
cd /d D:\SORTAN
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
py app.py


Open:
http://127.0.0.1:5000

Admin:
http://127.0.0.1:5000/admin/login

Default demo admin:
Username: admin
Password: sortan123

Change the admin credentials in `app.py` before deploying publicly.

## Production note

For real public deployment, use a production WSGI server, HTTPS, a strong secret key, a real database such as PostgreSQL, and a proper payment provider. The included SQLite version is designed as a complete local MVP and can be upgraded without changing the storefront concept.
"# SanDrop" 
