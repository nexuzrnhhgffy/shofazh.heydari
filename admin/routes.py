from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from werkzeug.utils import secure_filename
import os
from extensions import db
from models import (
    Product,
    ProductVariant,
    ProductAttribute,
    ProductImage,
    Attribute,
    Brand,
    Category,
    ArticleCategory,
    Article,
    ArticleComment,
    ContactMessage,
    SiteSetting,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="../templates/admin")

# simple hardcoded admin credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@admin_bp.before_request
def require_admin_login():
    # allow login page
    if request.endpoint == 'admin.login':
        return None
    # allow static file serving
    if request.endpoint and request.endpoint.endswith('static'):
        return None
    # check session
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login', next=request.path))


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    next_url = request.form.get('next') or request.args.get('next') or url_for('admin.dashboard')
    if username == ADMIN_USER and password == ADMIN_PASS:
        session['admin_logged_in'] = True
        return redirect(next_url)
    flash('نام کاربری یا رمز عبور اشتباه است.', 'danger')
    return render_template('login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))


@admin_bp.route("/dashboard")
def dashboard():
    product_count = Product.query.count()
    variant_count = ProductVariant.query.count()
    order_count = 0  # orders table exists; omitted for brevity

    low_stock = ProductVariant.query.filter(ProductVariant.stock_quantity < 5).limit(10).all()

    recent_orders = []  # simplified; implement later
    return render_template(
        "dashboard.html",
        product_count=product_count,
        variant_count=variant_count,
        order_count=order_count,
        low_stock=low_stock,
        recent_orders=recent_orders,
    )


@admin_bp.route("/products")
def products_list():
    # simple filters
    brand_id = request.args.get("brand_id")
    category_id = request.args.get("category_id")
    status = request.args.get("status")
    q = request.args.get("q")

    query = Product.query
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if status == "active":
        query = query.filter_by(is_active=True)
    if status == "inactive":
        query = query.filter_by(is_active=False)
    if q:
        query = query.filter(Product.product_name.contains(q))

    products = query.order_by(Product.created_at.desc()).all()
    brands = Brand.query.order_by(Brand.brand_name).all()
    categories = Category.query.order_by(Category.category_name).all()
    return render_template("products/list.html", products=products, brands=brands, categories=categories)


def save_image(file_storage):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "static/uploads")
    os.makedirs(upload_folder, exist_ok=True)
    path = os.path.join(upload_folder, filename)
    file_storage.save(path)
    return path


@admin_bp.route("/products/add", methods=["GET", "POST"])
def product_add():
    if request.method == "GET":
        brands = Brand.query.order_by(Brand.brand_name).all()
        categories = Category.query.order_by(Category.category_name).all()
        attributes = Attribute.query.order_by(Attribute.display_order).all()
        return render_template("products/form.html", brands=brands, categories=categories, attributes=attributes)

    # POST: collect form data
    data = request.form
    product_name = data.get("product_name")
    brand_id_raw = data.get("brand_id")
    category_id_raw = data.get("category_id")
    description = data.get("description")
    is_active = True if data.get("is_active") == "on" else False

    images = request.files.getlist("images")
    image_paths = []
    for img in images:
        if img and img.filename:
            path = save_image(img)
            if path:
                image_paths.append(path)

    # Set the first image as the main image_url for backward compatibility
    image_path = image_paths[0] if image_paths else None

    # Validate category and brand IDs
    try:
        category_id = int(category_id_raw) if category_id_raw else None
    except ValueError:
        category_id = None

    if category_id is None or not Category.query.get(category_id):
        flash("لطفاً دسته‌بندی معتبر انتخاب کنید.", "danger")
        return redirect(url_for("admin.product_add"))

    try:
        brand_id = int(brand_id_raw) if brand_id_raw else None
    except ValueError:
        brand_id = None

    if brand_id is not None and not Brand.query.get(brand_id):
        brand_id = None

    # create product
    product = Product(vendor_id=1, brand_id=brand_id or None, category_id=category_id, product_name=product_name, slug=(product_name or "").replace(" ", "-").lower(), description=description, image_url=image_path, is_active=is_active)
    db.session.add(product)
    db.session.flush()

    # Add product images
    for i, path in enumerate(image_paths):
        is_featured = (i == 0)  # First image is featured
        img = ProductImage(product_id=product.product_id, image_url=path, is_featured=is_featured, sort_order=i)
        db.session.add(img)

    # attributes: expect attributes[] pairs of attribute_id and value
    attr_ids = request.form.getlist("attribute_id")
    attr_vals = request.form.getlist("attribute_value")
    for aid, val in zip(attr_ids, attr_vals):
        if not aid or not val:
            continue
        pa = ProductAttribute(product_id=product.product_id, attribute_id=aid, value=val)
        db.session.add(pa)

    # variants: expect arrays
    skus = request.form.getlist("variant_sku")
    sizes = request.form.getlist("variant_size")
    units = request.form.getlist("variant_unit")
    wholes = request.form.getlist("variant_wholesale")
    rets = request.form.getlist("variant_retail")
    stocks = request.form.getlist("variant_stock")
    defaults = request.form.getlist("variant_default")

    for i, sku in enumerate(skus):
        if not sku:
            continue
        size = sizes[i] if i < len(sizes) else None
        unit = units[i] if i < len(units) else None
        wholesale = wholes[i] if i < len(wholes) else 0
        retail = rets[i] if i < len(rets) else 0
        stock = int(stocks[i]) if i < len(stocks) and stocks[i].isdigit() else 0
        is_def = False
        if defaults:
            # defaults is the name of radio group; request.form returns the selected value
            selected_default = request.form.get("variant_default_selected")
            is_def = (selected_default == sku)

        pv = ProductVariant(product_id=product.product_id, sku=sku, variant_name=f"{size} {unit}".strip(), size_value=size, size_unit=unit, wholesale_price=wholesale or 0, retail_price=retail or 0, stock_quantity=stock, is_default=is_def)
        db.session.add(pv)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Error saving product')
        flash('خطا در ذخیره محصول. لطفاً ورودی‌ها را بررسی کنید.', 'danger')
        return redirect(url_for('admin.product_add'))

    flash("محصول با موفقیت ذخیره شد.", "success")
    return redirect(url_for("admin.products_list"))


@admin_bp.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "GET":
        brands = Brand.query.order_by(Brand.brand_name).all()
        categories = Category.query.order_by(Category.category_name).all()
        attributes = Attribute.query.order_by(Attribute.display_order).all()
        return render_template("products/form.html", brands=brands, categories=categories, attributes=attributes, product=product)

    # POST: update
    data = request.form
    product.product_name = data.get("product_name")

    # Validate incoming IDs
    try:
        bid = int(data.get("brand_id")) if data.get("brand_id") else None
    except ValueError:
        bid = None
    product.brand_id = bid if (bid and Brand.query.get(bid)) else None

    try:
        cid = int(data.get("category_id")) if data.get("category_id") else None
    except ValueError:
        cid = None
    if cid is None or not Category.query.get(cid):
        flash("لطفاً دسته‌بندی معتبر انتخاب کنید.", "danger")
        return redirect(url_for("admin.product_edit", product_id=product.product_id))
    product.category_id = cid

    product.description = data.get("description")
    product.is_active = True if data.get("is_active") == "on" else False

    # Handle images
    existing_image_ids = set(request.form.getlist("existing_images"))
    # Delete images not in existing_image_ids
    ProductImage.query.filter(ProductImage.product_id == product.product_id, ~ProductImage.image_id.in_(existing_image_ids)).delete()

    # Add new images
    images = request.files.getlist("images")
    new_image_paths = []
    for img in images:
        if img and img.filename:
            path = save_image(img)
            if path:
                new_image_paths.append(path)

    # Add new ProductImage entries
    for path in new_image_paths:
        img = ProductImage(product_id=product.product_id, image_url=path, sort_order=0)  # sort_order can be updated later
        db.session.add(img)

    # Update main image_url if needed (set to first image if exists)
    first_image = ProductImage.query.filter_by(product_id=product.product_id, is_featured=True).first()
    if first_image:
        product.image_url = first_image.image_url
    elif new_image_paths:
        product.image_url = new_image_paths[0]
    # If no images, keep existing or set to None

    # attributes: delete existing and insert new for simplicity
    ProductAttribute.query.filter_by(product_id=product.product_id).delete()
    attr_ids = request.form.getlist("attribute_id")
    attr_vals = request.form.getlist("attribute_value")
    for aid, val in zip(attr_ids, attr_vals):
        if not aid or not val:
            continue
        pa = ProductAttribute(product_id=product.product_id, attribute_id=aid, value=val)
        db.session.add(pa)

    # variants: simple approach: delete all and recreate (keep sku uniqueness in DB)
    ProductVariant.query.filter_by(product_id=product.product_id).delete()
    skus = request.form.getlist("variant_sku")
    sizes = request.form.getlist("variant_size")
    units = request.form.getlist("variant_unit")
    wholes = request.form.getlist("variant_wholesale")
    rets = request.form.getlist("variant_retail")
    stocks = request.form.getlist("variant_stock")
    selected_default = request.form.get("variant_default_selected")

    for i, sku in enumerate(skus):
        if not sku:
            continue
        size = sizes[i] if i < len(sizes) else None
        unit = units[i] if i < len(units) else None
        wholesale = wholes[i] if i < len(wholes) else 0
        retail = rets[i] if i < len(rets) else 0
        stock = int(stocks[i]) if i < len(stocks) and stocks[i].isdigit() else 0
        is_def = (selected_default == sku)

        pv = ProductVariant(product_id=product.product_id, sku=sku, variant_name=f"{size} {unit}".strip(), size_value=size, size_unit=unit, wholesale_price=wholesale or 0, retail_price=retail or 0, stock_quantity=stock, is_default=is_def)
        db.session.add(pv)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Error updating product')
        flash('خطا در به‌روزرسانی محصول. لطفاً ورودی‌ها را بررسی کنید.', 'danger')
        return redirect(url_for('admin.product_edit', product_id=product.product_id))

    flash("محصول با موفقیت به‌روزرسانی شد.", "success")
    return redirect(url_for("admin.products_list"))


@admin_bp.route("/products/delete/<int:product_id>", methods=["POST"])
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    flash("محصول غیرفعال شد.", "warning")
    return redirect(url_for("admin.products_list"))


# API endpoints
@admin_bp.route("/api/attributes")
def api_attributes():
    attrs = Attribute.query.order_by(Attribute.display_order).all()
    data = [{"attribute_id": a.attribute_id, "attribute_name": a.attribute_name, "attribute_type": a.attribute_type} for a in attrs]
    return jsonify(data)


@admin_bp.route("/api/generate-sku", methods=["POST"])
def api_generate_sku():
    payload = request.json or {}
    name = payload.get("product_name", "")
    size = payload.get("size", "")
    brand = payload.get("brand", "")

    def slugify(s):
        return "".join(ch for ch in s.upper().replace(" ", "-") if ch.isalnum() or ch == "-")

    prefix = (brand or name)[:10]
    sku = f"{slugify(prefix)}-{slugify(str(size))}" if size else slugify(prefix)
    # ensure uniqueness
    exists = ProductVariant.query.filter_by(sku=sku).first()
    counter = 1
    base = sku
    while exists:
        sku = f"{base}-{counter}"
        exists = ProductVariant.query.filter_by(sku=sku).first()
        counter += 1
    return jsonify({"sku": sku})


@admin_bp.route("/api/check-sku", methods=["POST"])
def api_check_sku():
    payload = request.json or {}
    sku = payload.get("sku")
    exists = False
    if sku:
        exists = bool(ProductVariant.query.filter_by(sku=sku).first())
    return jsonify({"available": not exists})


# Categories (گروه محصولات)
@admin_bp.route("/categories")
def categories_list():
    q = request.args.get("q")
    query = Category.query
    if q:
        query = query.filter(Category.category_name.contains(q))
    categories = query.order_by(Category.sort_order, Category.category_name).all()
    return render_template("categories/list.html", categories=categories)


@admin_bp.route("/categories/add", methods=["GET", "POST"])
def category_add():
    if request.method == "GET":
        parent_categories = Category.query.filter(Category.parent_id.is_(None)).order_by(Category.category_name).all()
        return render_template("categories/form.html", parent_categories=parent_categories)

    data = request.form
    category_name = data.get("category_name")
    parent_id = data.get("parent_id")
    is_active = True if data.get("is_active") == "on" else False
    sort_order = int(data.get("sort_order", 0))

    if not category_name:
        flash("نام دسته‌بندی الزامی است.", "danger")
        return redirect(url_for("admin.category_add"))

    slug = category_name.replace(" ", "-").lower()
    existing = Category.query.filter_by(slug=slug).first()


# Site settings admin
@admin_bp.route("/site-settings")
def site_settings_list():
    settings = SiteSetting.query.order_by(SiteSetting.key).all()
    return render_template("site_settings/list.html", settings=settings)


@admin_bp.route("/site-settings/edit/<string:key>", methods=["GET", "POST"])
def site_setting_edit(key):
    # support creating a new key via /site-settings/edit/new?key=the_key
    if key == 'new' and request.method == 'GET':
        proposed = request.args.get('key', '').strip()
        if not proposed:
            flash('کلید جدید مشخص نشده است.', 'warning')
            return redirect(url_for('admin.site_settings_list'))
        key = proposed

    s = SiteSetting.query.get(key)
    if request.method == "POST":
        # allow creating when coming from the "new" flow
        form_key = request.form.get('key') or key
        value = request.form.get("value")
        if s:
            s.value = value
        else:
            s = SiteSetting(key=form_key, value=value)
            db.session.add(s)
        db.session.commit()
        flash('تنظیمات ذخیره شد.', 'success')
        return redirect(url_for('admin.site_settings_list'))
    return render_template('site_settings/form.html', setting=s, key=key)


@admin_bp.route('/site-settings/toggle/<string:key>', methods=['POST'])
def site_setting_toggle(key):
    s = SiteSetting.query.get_or_404(key)
    s.is_active = not bool(s.is_active)
    db.session.commit()
    flash('وضعیت تنظیم تغییر کرد.', 'success')
    return redirect(url_for('admin.site_settings_list'))


@admin_bp.route('/site-settings/delete/<string:key>', methods=['POST'])
def site_setting_delete(key):
    s = SiteSetting.query.get_or_404(key)
    db.session.delete(s)
    db.session.commit()
    flash('تنظیم حذف شد.', 'warning')
    return redirect(url_for('admin.site_settings_list'))
    if existing:
        slug = f"{slug}-{Category.query.count() + 1}"

    category = Category(
        category_name=category_name,
        slug=slug,
        parent_id=int(parent_id) if parent_id else None,
        is_active=is_active,
        sort_order=sort_order
    )
    db.session.add(category)
    db.session.commit()
    flash("دسته‌بندی با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.categories_list"))


@admin_bp.route("/categories/edit/<int:category_id>", methods=["GET", "POST"])
def category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == "GET":
        parent_categories = Category.query.filter(Category.parent_id.is_(None), Category.category_id != category_id).order_by(Category.category_name).all()
        return render_template("categories/form.html", category=category, parent_categories=parent_categories)

    data = request.form
    category.category_name = data.get("category_name")
    parent_id = data.get("parent_id")
    category.is_active = True if data.get("is_active") == "on" else False
    category.sort_order = int(data.get("sort_order", 0))

    if not category.category_name:
        flash("نام دسته‌بندی الزامی است.", "danger")
        return redirect(url_for("admin.category_edit", category_id=category_id))

    category.slug = category.category_name.replace(" ", "-").lower()
    category.parent_id = int(parent_id) if parent_id else None

    db.session.commit()
    flash("دسته‌بندی با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.categories_list"))


@admin_bp.route("/categories/delete/<int:category_id>", methods=["POST"])
def category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    category.is_active = False
    db.session.commit()
    flash("دسته‌بندی غیرفعال شد.", "warning")
    return redirect(url_for("admin.categories_list"))


# Attributes (ویژگی‌ها)
@admin_bp.route("/attributes")
def attributes_list():
    q = request.args.get("q")
    query = Attribute.query
    if q:
        query = query.filter(Attribute.attribute_name.contains(q))
    attributes = query.order_by(Attribute.display_order, Attribute.attribute_name).all()
    return render_template("attributes/list.html", attributes=attributes)


@admin_bp.route("/attributes/add", methods=["GET", "POST"])
def attribute_add():
    if request.method == "GET":
        return render_template("attributes/form.html")

    data = request.form
    attribute_name = data.get("attribute_name")
    attribute_type = data.get("attribute_type", "text")
    is_filterable = True if data.get("is_filterable") == "on" else False
    display_order = int(data.get("display_order", 0))

    if not attribute_name:
        flash("نام ویژگی الزامی است.", "danger")
        return redirect(url_for("admin.attribute_add"))

    attribute = Attribute(
        attribute_name=attribute_name,
        attribute_type=attribute_type,
        is_filterable=is_filterable,
        display_order=display_order
    )
    db.session.add(attribute)
    db.session.commit()
    flash("ویژگی با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.attributes_list"))


@admin_bp.route("/attributes/edit/<int:attribute_id>", methods=["GET", "POST"])
def attribute_edit(attribute_id):
    attribute = Attribute.query.get_or_404(attribute_id)
    if request.method == "GET":
        return render_template("attributes/form.html", attribute=attribute)

    data = request.form
    attribute.attribute_name = data.get("attribute_name")
    attribute.attribute_type = data.get("attribute_type", "text")
    attribute.is_filterable = True if data.get("is_filterable") == "on" else False
    attribute.display_order = int(data.get("display_order", 0))

    if not attribute.attribute_name:
        flash("نام ویژگی الزامی است.", "danger")
        return redirect(url_for("admin.attribute_edit", attribute_id=attribute_id))

    db.session.commit()
    flash("ویژگی با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.attributes_list"))


@admin_bp.route("/attributes/delete/<int:attribute_id>", methods=["POST"])
def attribute_delete(attribute_id):
    attribute = Attribute.query.get_or_404(attribute_id)
    # Check if used in products
    if ProductAttribute.query.filter_by(attribute_id=attribute_id).first():
        flash("این ویژگی در محصولات استفاده شده و نمی‌توان حذف کرد.", "danger")
        return redirect(url_for("admin.attributes_list"))
    
    db.session.delete(attribute)
    db.session.commit()
    flash("ویژگی حذف شد.", "warning")
    return redirect(url_for("admin.attributes_list"))


# Article Categories (گروه مقالات)
@admin_bp.route("/article-categories")
def article_categories_list():
    q = request.args.get("q")
    query = ArticleCategory.query
    if q:
        query = query.filter(ArticleCategory.name.contains(q))
    categories = query.order_by(ArticleCategory.sort_order, ArticleCategory.name).all()
    return render_template("article_categories/list.html", categories=categories)


@admin_bp.route("/article-categories/add", methods=["GET", "POST"])
def article_category_add():
    if request.method == "GET":
        parent_categories = ArticleCategory.query.filter(ArticleCategory.parent_id.is_(None)).order_by(ArticleCategory.name).all()
        return render_template("article_categories/form.html", parent_categories=parent_categories)

    data = request.form
    name = data.get("name")
    description = data.get("description")
    parent_id = data.get("parent_id")
    is_active = True if data.get("is_active") == "on" else False
    sort_order = int(data.get("sort_order", 0))

    image = request.files.get("image")
    image_path = save_image(image) if image else None

    if not name:
        flash("نام دسته‌بندی الزامی است.", "danger")
        return redirect(url_for("admin.article_category_add"))

    slug = name.replace(" ", "-").lower()
    existing = ArticleCategory.query.filter_by(slug=slug).first()
    if existing:
        slug = f"{slug}-{ArticleCategory.query.count() + 1}"

    category = ArticleCategory(
        name=name,
        slug=slug,
        description=description,
        parent_id=int(parent_id) if parent_id else None,
        image_url=image_path,
        is_active=is_active,
        sort_order=sort_order
    )
    db.session.add(category)
    db.session.commit()
    flash("دسته‌بندی مقاله با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.article_categories_list"))


@admin_bp.route("/article-categories/edit/<int:category_id>", methods=["GET", "POST"])
def article_category_edit(category_id):
    category = ArticleCategory.query.get_or_404(category_id)
    if request.method == "GET":
        parent_categories = ArticleCategory.query.filter(ArticleCategory.parent_id.is_(None), ArticleCategory.category_id != category_id).order_by(ArticleCategory.name).all()
        return render_template("article_categories/form.html", category=category, parent_categories=parent_categories)

    data = request.form
    category.name = data.get("name")
    category.description = data.get("description")
    parent_id = data.get("parent_id")
    category.is_active = True if data.get("is_active") == "on" else False
    category.sort_order = int(data.get("sort_order", 0))

    image = request.files.get("image")
    if image:
        image_path = save_image(image)
        category.image_url = image_path

    if not category.name:
        flash("نام دسته‌بندی الزامی است.", "danger")
        return redirect(url_for("admin.article_category_edit", category_id=category_id))

    category.slug = category.name.replace(" ", "-").lower()
    category.parent_id = int(parent_id) if parent_id else None

    db.session.commit()
    flash("دسته‌بندی مقاله با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.article_categories_list"))


@admin_bp.route("/article-categories/delete/<int:category_id>", methods=["POST"])
def article_category_delete(category_id):
    category = ArticleCategory.query.get_or_404(category_id)
    category.is_active = False
    db.session.commit()
    flash("دسته‌بندی مقاله غیرفعال شد.", "warning")
    return redirect(url_for("admin.article_categories_list"))


# Articles (مقالات)
@admin_bp.route("/articles")
def articles_list():
    q = request.args.get("q")
    category_id = request.args.get("category_id")
    status = request.args.get("status")

    query = Article.query
    if q:
        query = query.filter(Article.title.contains(q))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if status == "published":
        query = query.filter_by(is_published=True)
    elif status == "draft":
        query = query.filter_by(is_published=False)

    articles = query.order_by(Article.created_at.desc()).all()
    categories = ArticleCategory.query.order_by(ArticleCategory.name).all()
    return render_template("articles/list.html", articles=articles, categories=categories)


@admin_bp.route("/articles/add", methods=["GET", "POST"])
def article_add():
    if request.method == "GET":
        categories = ArticleCategory.query.order_by(ArticleCategory.name).all()
        return render_template("articles/form.html", categories=categories)

    data = request.form
    title = data.get("title")
    category_id = data.get("category_id")
    short_description = data.get("short_description")
    content = data.get("content")
    meta_title = data.get("meta_title")
    meta_description = data.get("meta_description")
    meta_keywords = data.get("meta_keywords")
    author_name = data.get("author_name")
    is_published = True if data.get("is_published") == "on" else False
    is_featured = True if data.get("is_featured") == "on" else False

    featured_image = request.files.get("featured_image")
    thumbnail_image = request.files.get("thumbnail_image")
    featured_path = save_image(featured_image) if featured_image else None
    thumbnail_path = save_image(thumbnail_image) if thumbnail_image else None

    if not title or not category_id or not content:
        flash("عنوان، دسته‌بندی و محتوا الزامی هستند.", "danger")
        return redirect(url_for("admin.article_add"))

    slug = title.replace(" ", "-").lower()
    existing = Article.query.filter_by(slug=slug).first()
    if existing:
        slug = f"{slug}-{Article.query.count() + 1}"

    article = Article(
        title=title,
        slug=slug,
        category_id=int(category_id),
        short_description=short_description,
        content=content,
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=meta_keywords,
        featured_image=featured_path,
        thumbnail_image=thumbnail_path,
        author_name=author_name,
        is_published=is_published,
        is_featured=is_featured,
        published_at=db.func.now() if is_published else None
    )
    db.session.add(article)
    db.session.commit()
    flash("مقاله با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.articles_list"))


@admin_bp.route("/articles/edit/<int:article_id>", methods=["GET", "POST"])
def article_edit(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == "GET":
        categories = ArticleCategory.query.order_by(ArticleCategory.name).all()
        return render_template("articles/form.html", article=article, categories=categories)

    data = request.form
    article.title = data.get("title")
    article.category_id = int(data.get("category_id"))
    article.short_description = data.get("short_description")
    article.content = data.get("content")
    article.meta_title = data.get("meta_title")
    article.meta_description = data.get("meta_description")
    article.meta_keywords = data.get("meta_keywords")
    article.author_name = data.get("author_name")
    article.is_published = True if data.get("is_published") == "on" else False
    article.is_featured = True if data.get("is_featured") == "on" else False

    featured_image = request.files.get("featured_image")
    thumbnail_image = request.files.get("thumbnail_image")
    if featured_image:
        featured_path = save_image(featured_image)
        article.featured_image = featured_path
    if thumbnail_image:
        thumbnail_path = save_image(thumbnail_image)
        article.thumbnail_image = thumbnail_path

    if not article.title or not article.category_id or not article.content:
        flash("عنوان، دسته‌بندی و محتوا الزامی هستند.", "danger")
        return redirect(url_for("admin.article_edit", article_id=article_id))

    article.slug = article.title.replace(" ", "-").lower()
    if article.is_published and not article.published_at:
        article.published_at = db.func.now()

    db.session.commit()
    flash("مقاله با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.articles_list"))


@admin_bp.route("/articles/delete/<int:article_id>", methods=["POST"])
def article_delete(article_id):
    article = Article.query.get_or_404(article_id)
    article.is_active = False
    db.session.commit()
    flash("مقاله غیرفعال شد.", "warning")
    return redirect(url_for("admin.articles_list"))


# Article Comments (کامنت مقالات)
@admin_bp.route("/article-comments")
def article_comments_list():
    q = request.args.get("q")
    status = request.args.get("status")

    query = ArticleComment.query.join(Article).filter(Article.is_active == True)
    if q:
        query = query.filter(db.or_(ArticleComment.author_name.contains(q), ArticleComment.content.contains(q)))
    if status == "approved":
        query = query.filter_by(is_approved=True)
    elif status == "pending":
        query = query.filter_by(is_approved=False)
    elif status == "spam":
        query = query.filter_by(is_spam=True)

    comments = query.order_by(ArticleComment.created_at.desc()).all()
    return render_template("article_comments/list.html", comments=comments)


@admin_bp.route("/article-comments/approve/<int:comment_id>", methods=["POST"])
def article_comment_approve(comment_id):
    comment = ArticleComment.query.get_or_404(comment_id)
    comment.is_approved = True
    comment.is_spam = False
    db.session.commit()
    flash("کامنت تایید شد.", "success")
    return redirect(url_for("admin.article_comments_list"))


@admin_bp.route("/article-comments/spam/<int:comment_id>", methods=["POST"])
def article_comment_spam(comment_id):
    comment = ArticleComment.query.get_or_404(comment_id)
    comment.is_spam = True
    comment.is_approved = False
    db.session.commit()
    flash("کامنت به عنوان اسپم标记 شد.", "warning")
    return redirect(url_for("admin.article_comments_list"))


@admin_bp.route("/article-comments/delete/<int:comment_id>", methods=["POST"])
def article_comment_delete(comment_id):
    comment = ArticleComment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash("کامنت حذف شد.", "danger")
    return redirect(url_for("admin.article_comments_list"))


# Brands (برندها)
@admin_bp.route("/brands")
def brands_list():
    q = request.args.get("q")
    query = Brand.query
    if q:
        query = query.filter(Brand.brand_name.contains(q))
    brands = query.order_by(Brand.brand_name).all()
    return render_template("brands/list.html", brands=brands)


@admin_bp.route("/brands/add", methods=["GET", "POST"])
def brand_add():
    if request.method == "GET":
        return render_template("brands/form.html")

    data = request.form
    brand_name = data.get("brand_name")
    english_name = data.get("english_name")
    description = data.get("description")
    is_active = True if data.get("is_active") == "on" else False

    logo = request.files.get("logo")
    logo_path = save_image(logo) if logo else None

    if not brand_name:
        flash("نام برند الزامی است.", "danger")
        return redirect(url_for("admin.brand_add"))

    brand = Brand(brand_name=brand_name, english_name=english_name, description=description, logo_url=logo_path, is_active=is_active)
    db.session.add(brand)
    db.session.commit()
    flash("برند با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.brands_list"))


@admin_bp.route("/brands/edit/<int:brand_id>", methods=["GET", "POST"])
def brand_edit(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    if request.method == "GET":
        return render_template("brands/form.html", brand=brand)

    data = request.form
    brand.brand_name = data.get("brand_name")
    brand.english_name = data.get("english_name")
    brand.description = data.get("description")
    brand.is_active = True if data.get("is_active") == "on" else False

    logo = request.files.get("logo")
    if logo:
        logo_path = save_image(logo)
        brand.logo_url = logo_path

    if not brand.brand_name:
        flash("نام برند الزامی است.", "danger")
        return redirect(url_for("admin.brand_edit", brand_id=brand_id))

    db.session.commit()
    flash("برند با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.brands_list"))


@admin_bp.route("/brands/delete/<int:brand_id>", methods=["POST"])
def brand_delete(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    # Check if used in products
    if Product.query.filter_by(brand_id=brand_id).first():
        flash("این برند در محصولات استفاده شده و نمی‌توان حذف کرد.", "danger")
        return redirect(url_for("admin.brands_list"))
    
    db.session.delete(brand)
    db.session.commit()
    flash("برند حذف شد.", "warning")
    return redirect(url_for("admin.brands_list"))


# Variants (واریانت‌ها)
@admin_bp.route("/variants")
def variants_list():
    q = request.args.get("q")
    product_id = request.args.get("product_id")
    status = request.args.get("status")

    query = ProductVariant.query.join(Product)
    if q:
        query = query.filter(db.or_(ProductVariant.sku.contains(q), ProductVariant.variant_name.contains(q)))
    if product_id:
        query = query.filter_by(product_id=product_id)
    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    variants = query.order_by(ProductVariant.created_at.desc()).all()
    products = Product.query.order_by(Product.product_name).all()
    return render_template("variants/list.html", variants=variants, products=products)


@admin_bp.route("/variants/add", methods=["GET", "POST"])
def variant_add():
    if request.method == "GET":
        products = Product.query.order_by(Product.product_name).all()
        return render_template("variants/form.html", products=products)

    data = request.form
    product_id = data.get("product_id")
    sku = data.get("sku")
    variant_name = data.get("variant_name")
    size_value = data.get("size_value")
    size_unit = data.get("size_unit")
    wholesale_price = data.get("wholesale_price")
    retail_price = data.get("retail_price")
    stock_quantity = int(data.get("stock_quantity", 0))
    is_active = True if data.get("is_active") == "on" else False
    is_default = True if data.get("is_default") == "on" else False

    if not product_id or not sku:
        flash("محصول و SKU الزامی هستند.", "danger")
        return redirect(url_for("admin.variant_add"))

    # Check SKU uniqueness
    if ProductVariant.query.filter_by(sku=sku).first():
        flash("SKU تکراری است.", "danger")
        return redirect(url_for("admin.variant_add"))

    variant = ProductVariant(
        product_id=int(product_id),
        sku=sku,
        variant_name=variant_name,
        size_value=size_value,
        size_unit=size_unit,
        wholesale_price=float(wholesale_price) if wholesale_price else 0,
        retail_price=float(retail_price) if retail_price else 0,
        stock_quantity=stock_quantity,
        is_active=is_active,
        is_default=is_default
    )
    db.session.add(variant)
    db.session.commit()
    flash("واریانت با موفقیت اضافه شد.", "success")
    return redirect(url_for("admin.variants_list"))


@admin_bp.route("/variants/edit/<int:variant_id>", methods=["GET", "POST"])
def variant_edit(variant_id):
    variant = ProductVariant.query.get_or_404(variant_id)
    if request.method == "GET":
        products = Product.query.order_by(Product.product_name).all()
        return render_template("variants/form.html", variant=variant, products=products)

    data = request.form
    variant.product_id = int(data.get("product_id"))
    sku = data.get("sku")
    variant.variant_name = data.get("variant_name")
    variant.size_value = data.get("size_value")
    variant.size_unit = data.get("size_unit")
    variant.wholesale_price = float(data.get("wholesale_price")) if data.get("wholesale_price") else 0
    variant.retail_price = float(data.get("retail_price")) if data.get("retail_price") else 0
    variant.stock_quantity = int(data.get("stock_quantity", 0))
    variant.is_active = True if data.get("is_active") == "on" else False
    variant.is_default = True if data.get("is_default") == "on" else False

    if not variant.product_id or not sku:
        flash("محصول و SKU الزامی هستند.", "danger")
        return redirect(url_for("admin.variant_edit", variant_id=variant_id))

    # Check SKU uniqueness
    existing = ProductVariant.query.filter_by(sku=sku).first()
    if existing and existing.variant_id != variant_id:
        flash("SKU تکراری است.", "danger")
        return redirect(url_for("admin.variant_edit", variant_id=variant_id))

    variant.sku = sku
    db.session.commit()
    flash("واریانت با موفقیت ویرایش شد.", "success")
    return redirect(url_for("admin.variants_list"))


@admin_bp.route("/contact-messages")
def contact_messages_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("contact_messages/list.html", messages=messages)


@admin_bp.route("/contact-messages/<int:message_id>", methods=["GET", "POST"])
def contact_message_detail(message_id):
    message = ContactMessage.query.get_or_404(message_id)
    if request.method == "POST":
        response = request.form.get("response", "").strip()
        message.response = response
        message.is_responded = True
        db.session.commit()
        flash("پاسخ ارسال شد.", "success")
        return redirect(url_for("admin.contact_messages_list"))
    return render_template("contact_messages/detail.html", message=message)
