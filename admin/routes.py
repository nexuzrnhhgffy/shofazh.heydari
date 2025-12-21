from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from extensions import db
from models import (
    Product,
    ProductVariant,
    ProductAttribute,
    Attribute,
    Brand,
    Category,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="../templates/admin")


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

    image = request.files.get("image")
    image_path = save_image(image) if image else None

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

    image = request.files.get("image")
    if image:
        image_path = save_image(image)
        product.image_url = image_path

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
