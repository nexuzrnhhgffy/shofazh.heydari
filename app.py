import os
from flask import Flask, render_template, request

from extensions import db
from models import Product, Category, Brand

app = Flask(__name__)
app.config.setdefault("UPLOAD_FOLDER", "static/uploads")
app.config.setdefault("SECRET_KEY", "dev-secret")
# Prefer DATABASE_URL env var if provided; otherwise fall back to local sqlite for dev
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL") or "sqlite:///hvac.db"

# initialize extensions
db.init_app(app)

# Ensure application-level secret_key is explicitly set (fixes session/flash errors)
app.secret_key = app.config.get('SECRET_KEY') or "dev-secret"

# Jinja filter: format number as currency (with thousand separators and Farsi 'تومان')
@app.template_filter('currency')
def currency(value):
    try:
        if value is None:
            return 'قیمت ندارد'
        return f"{int(value):,} تومان"
    except Exception:
        return 'قیمت ندارد'

# register admin blueprint
try:
    from admin.routes import admin_bp
    app.register_blueprint(admin_bp)
except Exception:
    pass


@app.route('/')
def index():
    categories = Category.query.filter_by(parent_id=None).order_by(Category.category_name).all()
    featured_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template('index.html', categories=categories, featured_products=featured_products)


@app.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    variants = product.variants
    attributes = [(pa.attribute.attribute_name, pa.value) for pa in product.attributes]
    related = Product.query.filter(Product.category_id == product.category_id, Product.product_id != product.product_id, Product.is_active == True).limit(4).all()
    default_price = None
    if variants:
        default_variant = next((v for v in variants if v.is_default), variants[0])
        default_price = default_variant.retail_price
    return render_template('product.html', product=product, variants=variants, attributes=attributes, related=related, default_price=default_price)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 12
    category_id = request.args.get('category_id')
    brand_id = request.args.get('brand_id')

    query = Product.query.filter(Product.is_active == True)
    if q:
        query = query.filter(Product.product_name.contains(q) | Product.description.contains(q))
    if category_id:
        try:
            cid = int(category_id)
            query = query.filter(Product.category_id == cid)
        except ValueError:
            pass
    if brand_id:
        try:
            bid = int(brand_id)
            query = query.filter(Product.brand_id == bid)
        except ValueError:
            pass

    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    categories = Category.query.order_by(Category.category_name).all()
    brands = Brand.query.order_by(Brand.brand_name).all()
    return render_template('search.html', q=q, products=products, total=total, categories=categories, brands=brands)


@app.route('/products')
def products():
    page = int(request.args.get('page', 1))
    per_page = 20
    query = Product.query.filter(Product.is_active == True)
    products = query.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return render_template('products.html', products=products)


if __name__ == '__main__':
    app.run(debug=True)
