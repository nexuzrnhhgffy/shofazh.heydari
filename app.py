import os
from flask import Flask, render_template, request

from extensions import db
from models import Product, Category, Brand,ArticleCategory, Article, ContactMessage, SiteSetting

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


@app.context_processor
def inject_menu_categories():
    try:
        rows = db.session.query(
            Category,
            db.func.count(Product.product_id).label('pcount')
        ).outerjoin(Product, Product.category_id == Category.category_id)
        rows = rows.filter(Category.parent_id == None)
        rows = rows.group_by(Category.category_id).order_by(db.func.count(Product.product_id).desc()).limit(3).all()
        categories = [r[0] for r in rows]
        return dict(menu_categories=categories)
    except Exception:
        try:
            categories = Category.query.filter_by(parent_id=None).order_by(Category.category_name).limit(3).all()
            return dict(menu_categories=categories)
        except Exception:
            return dict(menu_categories=[])


def _get_setting_value(key, default=None):
    try:
        row = SiteSetting.query.filter_by(key=key, is_active=True).first()
        if row and row.value is not None:
            return row.value
    except Exception:
        pass
    return default


# Jinja filter to render numeric substrings left-to-right (useful for phone numbers)
def ltr_numbers(value):
    try:
        import re
        from markupsafe import Markup

        if value is None:
            return ''
        s = str(value)
        # match runs that contain at least two digits and may include + - () and spaces
        pattern = re.compile(r"(\+?\d[\d\-\s\(\)]{1,}\d)")

        def repl(m):
            return f"<span class=\"ltr-num\" dir=\"ltr\">{m.group(1)}</span>"

        result = pattern.sub(repl, s)
        return Markup(result)
    except Exception:
        return value


# register the filter
app.jinja_env.filters['ltr_numbers'] = ltr_numbers


@app.context_processor
def inject_site_texts():
    # Provide a dict `site_texts` to templates with DB-backed values and fallbacks
    ticker_raw = _get_setting_value('ticker_items')
    if ticker_raw:
        # stored as newline-separated or JSON; simple split by newlines
        ticker_items = [s.strip() for s in ticker_raw.split('\n') if s.strip()]
    else:
        ticker_items = [
            'واتساپ: 0912 926 5458',
            'ارسال رایگان تهران و کرج',
            'نصب حرفه‌ای پکیج و رادیاتور',
            'ضمانت اصالت کالا',
            'مشاوره رایگان تأسیسات'
        ]

    logo_text = _get_setting_value('logo_text', 'شوفاژ حیدری')

    footer_about = _get_setting_value('footer_about', 'تأمین کننده تجهیزات تأسیسات ساختمان با بهترین قیمت و ضمانت اصالت')

    contact_phone = _get_setting_value('contact_phone', '021-55661234')
    contact_mobile = _get_setting_value('contact_mobile', '09121234567')

    return dict(site_texts={
        'ticker_items': ticker_items,
        'logo_text': logo_text,
        'footer_about': footer_about,
        'contact_phone': contact_phone,
        'contact_mobile': contact_mobile,
    })


@app.route('/')
def index():
    try:
        categories = Category.query.filter_by(parent_id=None).order_by(Category.category_name).all() or []
    except Exception:
        categories = []
    try:
        featured_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all() or []
    except Exception:
        featured_products = []
    try:
        article_categories = ArticleCategory.query.filter_by(
            parent_id=None,
            is_active=True
        ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all() or []
    except Exception:
        article_categories = []
    try:
        brands = Brand.query.filter_by(is_active=True).order_by(Brand.brand_name).all() or []
    except Exception:
        brands = []
    return render_template('index.html', categories=categories, featured_products=featured_products, article_categories=article_categories, brands=brands)

 


@app.route('/product/<slug>')
def product_detail(slug):
    try:
        product = db.session.query(Product).options(db.selectinload(Product.images)).filter_by(slug=slug, is_active=True).first_or_404()
    except Exception:
        return render_template('product.html', product=None), 404
    variants = product.variants
    attributes = [(pa.attribute.attribute_name, pa.value) for pa in product.attributes]
    related = Product.query.filter(Product.category_id == product.category_id, Product.product_id != product.product_id, Product.is_active == True).limit(4).all()
    default_price = None
    default_variant = None
    if variants:
        default_variant = next((v for v in variants if v.is_default), variants[0])
        default_price = default_variant.retail_price
    return render_template('product.html', product=product, variants=variants, attributes=attributes, related=related, default_price=default_price, default_variant=default_variant)
 
@app.route('/blog/<slug>')
def blog_detail(slug):
    try:
        article = Article.query.filter_by(slug=slug, is_active=True).first_or_404()
    except Exception:
        return render_template('blog-detail.html', article=None, related_articles=[]), 404

    try:
        article.view_count = (article.view_count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        related_articles = Article.query.filter(
            Article.category_id == article.category_id,
            Article.article_id != article.article_id,
            Article.is_active == True
        ).order_by(Article.created_at.desc()).limit(3).all() or []
    except Exception:
        related_articles = []

    return render_template(
        'blog-detail.html',
        article=article,
        related_articles=related_articles
    )

@app.route('/blog')
def blog_list():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    try:
        articles = Article.query.filter_by(is_active=True)\
            .order_by(Article.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
    except Exception:
        articles = []

    try:
        article_categories = ArticleCategory.query.filter_by(
            parent_id=None,
            is_active=True
        ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all() or []
    except Exception:
        article_categories = []

    return render_template(
        'blog.html',
        articles=articles,
        article_categories=article_categories
    )

@app.route('/blog/category/<int:category_id>')
def blog_category(category_id):
    page = request.args.get('page', 1, type=int)
    per_page = 12
    try:
        category = ArticleCategory.query.filter_by(category_id=category_id, is_active=True).first_or_404()
    except Exception:
        return render_template('blog.html', articles=[], article_categories=[], current_category=None), 404

    try:
        articles = Article.query.filter_by(category_id=category_id, is_active=True)\
            .order_by(Article.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
    except Exception:
        articles = []

    try:
        article_categories = ArticleCategory.query.filter_by(
            parent_id=None,
            is_active=True
        ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all() or []
    except Exception:
        article_categories = []

    return render_template(
        'blog.html',
        articles=articles,
        article_categories=article_categories,
        current_category=category
    )



@app.route('/products')
def products():
    page = int(request.args.get('page', 1))
    per_page = 20
    try:
        query = Product.query.filter(Product.is_active == True)
        products = query.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    except Exception:
        products = []
    return render_template('products.html', products=products)




@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()
        
        # Validation
        if not phone or not message:
            return render_template('contact.html', error="شماره تماس و پیام اجباری هستند.")
        
        # Rate limiting: check if user sent a message in the last 5 minutes
        ip = request.remote_addr
        recent_message = ContactMessage.query.filter_by(ip_address=ip).filter(
            ContactMessage.created_at > db.func.now() - db.text("INTERVAL 5 MINUTE")
        ).first()
        if recent_message:
            return render_template('contact.html', error="شما نمی‌توانید در کمتر از ۵ دقیقه پیام ارسال کنید.")
        
        # Save message
        new_message = ContactMessage(
            name=name if name else None,
            phone=phone,
            email=email if email else None,
            message=message,
            ip_address=ip,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(new_message)
        db.session.commit()
        
        return render_template('contact.html', success="پیام شما با موفقیت ارسال شد.")
    
    return render_template('contact.html')






@app.route('/search')
def search():
    # Read query and filter/sort params
    q = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 12
    category_ids = request.args.getlist('category_id')
    brand_ids = request.args.getlist('brand_id')
    try:
        price_min = float(request.args.get('price_min')) if request.args.get('price_min') else None
    except Exception:
        price_min = None
    try:
        price_max = float(request.args.get('price_max')) if request.args.get('price_max') else None
    except Exception:
        price_max = None
    sort_by = request.args.get('sort', 'relevance')

    # Base product query
    products_q = Product.query.filter(Product.is_active == True)

    # Text query
    if q:
        products_q = products_q.filter(
            (Product.product_name.ilike(f'%{q}%')) |
            (Product.description.ilike(f'%{q}%')) |
            Product.brand.has(Brand.brand_name.ilike(f'%{q}%'))
        )

    # Category filter (allow multiple)
    if category_ids:
        ids = [int(x) for x in category_ids if str(x).isdigit()]
        if ids:
            products_q = products_q.filter(Product.category_id.in_(ids))

    # Brand filter (allow multiple)
    if brand_ids:
        ids = [int(x) for x in brand_ids if str(x).isdigit()]
        if ids:
            products_q = products_q.filter(Product.brand_id.in_(ids))

    # Price filter requires joining variants
    from models import ProductVariant
    joined_variants = False
    if price_min is not None or price_max is not None or sort_by in ('price-asc', 'price-desc'):
        products_q = products_q.join(Product.variants)
        joined_variants = True
        if price_min is not None:
            products_q = products_q.filter(ProductVariant.retail_price >= price_min)
        if price_max is not None:
            products_q = products_q.filter(ProductVariant.retail_price <= price_max)

    # Sorting
    if sort_by == 'price-asc':
        products_q = products_q.order_by(ProductVariant.retail_price.asc()) if joined_variants else products_q
    elif sort_by == 'price-desc':
        products_q = products_q.order_by(ProductVariant.retail_price.desc()) if joined_variants else products_q
    elif sort_by == 'newest':
        products_q = products_q.order_by(Product.created_at.desc())
    else:
        # relevance or default
        products_q = products_q.order_by(Product.created_at.desc())

    # Remove duplicates when joined with variants
    if joined_variants:
        products_q = products_q.group_by(Product.product_id)

    # Total count
    try:
        total = products_q.with_entities(db.func.count(Product.product_id)).scalar() or 0
    except Exception:
        try:
            total = products_q.count()
        except Exception:
            total = 0

    # Pagination
    try:
        products = products_q.offset((page - 1) * per_page).limit(per_page).all()
    except Exception:
        products = []

    # categories and brands for filters
    try:
        categories = Category.query.filter_by(is_active=True).order_by(Category.category_name).all()
    except Exception:
        categories = []
    try:
        brands = Brand.query.filter_by(is_active=True).order_by(Brand.brand_name).all()
    except Exception:
        brands = []

    return render_template('search.html', q=q, products=products, total=total, categories=categories, brands=brands, page=page, per_page=per_page, sort_by=sort_by)


if __name__ == '__main__':
    app.run(debug=True)
