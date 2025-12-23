import os
from flask import Flask, render_template, request

from extensions import db
from models import Product, Category, Brand,ArticleCategory, Article, ContactMessage

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
    article_categories = ArticleCategory.query.filter_by(
        parent_id=None,
        is_active=True
    ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all()
    return render_template('index.html', categories=categories, featured_products=featured_products, article_categories=article_categories)

 


@app.route('/product/<slug>')
def product_detail(slug):
    product = db.session.query(Product).options(db.selectinload(Product.images)).filter_by(slug=slug, is_active=True).first_or_404()
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
    article = Article.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    # افزایش تعداد بازدید
    article.view_count += 1
    db.session.commit()
    
    # مقالات مرتبط: از همان دسته، غیر از خودش، فعال، محدود به ۳ تا
    related_articles = Article.query.filter(
        Article.category_id == article.category_id,
        Article.id != article.id,
        Article.is_active == True
    ).order_by(Article.created_at.desc()).limit(3).all()
    
    return render_template(
        'blog-detail.html',
        article=article,
        related_articles=related_articles
    )

# اگر صفحه لیست مقالات ندارید، می‌توانید این روت را هم اضافه کنید
@app.route('/blog')
def blog_list():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    articles = Article.query.filter_by(is_active=True)\
        .order_by(Article.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    article_categories = ArticleCategory.query.filter_by(
        parent_id=None,
        is_active=True
    ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all()
    
    return render_template(
        'blog.html',
        articles=articles,
        article_categories=article_categories
    )

@app.route('/blog/category/<int:category_id>')
def blog_category(category_id):
    page = request.args.get('page', 1, type=int)
    per_page = 12
    category = ArticleCategory.query.filter_by(category_id=category_id, is_active=True).first_or_404()
    articles = Article.query.filter_by(category_id=category_id, is_active=True)\
        .order_by(Article.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    article_categories = ArticleCategory.query.filter_by(
        parent_id=None,
        is_active=True
    ).order_by(ArticleCategory.sort_order, ArticleCategory.name).all()
    
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
    query = Product.query.filter(Product.is_active == True)
    products = query.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
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
    query = request.args.get('q', '').strip()
    
    if not query:
        return render_template('search.html', query='', products=[], articles=[])
    
    # جستجو در محصولات (نام، توضیحات، برند، دسته)
    products = Product.query.filter(
        Product.is_active == True,
        (
            Product.product_name.ilike(f'%{query}%') |
            Product.description.ilike(f'%{query}%') |
            Product.brand.has(Brand.brand_name.ilike(f'%{query}%'))
        )
    ).order_by(Product.created_at.desc()).limit(20).all()
    
    # جستجو در مقالات (عنوان و محتوا)
    articles = Article.query.filter(
        Article.is_active == True,
        (
            Article.title.ilike(f'%{query}%') |
            Article.content.ilike(f'%{query}%')
        )
    ).order_by(Article.created_at.desc()).limit(10).all()
    
    return render_template(
        'search.html',
        query=query,
        products=products,
        articles=articles
    )


if __name__ == '__main__':
    app.run(debug=True)
