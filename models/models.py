from sqlalchemy import func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import backref
from extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class Vendor(db.Model, TimestampMixin):
    __tablename__ = "vendors"

    vendor_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    vendor_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

    products = db.relationship("Product", back_populates="vendor", lazy="select")

    def __repr__(self):
        return f"<Vendor {self.vendor_name}>"


class Brand(db.Model, TimestampMixin):
    __tablename__ = "brands"

    brand_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    brand_name = db.Column(db.String(255), nullable=False)
    english_name = db.Column(db.String(255))  # معادل انگلیسی برند
    description = db.Column(db.Text)
    logo_url = db.Column(db.String(500))  # لوگو برند
    is_active = db.Column(db.Boolean, default=True)

    products = db.relationship("Product", back_populates="brand", lazy="select")

    def __repr__(self):
        return f"<Brand {self.brand_name}>"


class Category(db.Model, TimestampMixin):
    __tablename__ = "categories"

    category_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    parent_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    category_name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    parent = db.relationship("Category", remote_side=[category_id], backref=backref("children", lazy="select"))
    products = db.relationship("Product", back_populates="category", lazy="select")

    def __repr__(self):
        return f"<Category {self.category_name}>"


class Product(db.Model, TimestampMixin):
    __tablename__ = "products"

    product_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    vendor_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("vendors.vendor_id"), nullable=False)
    brand_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("brands.brand_id"), nullable=True)
    category_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("categories.category_id"), nullable=False)
    product_name = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), unique=True, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)

    vendor = db.relationship("Vendor", back_populates="products", lazy="joined")
    brand = db.relationship("Brand", back_populates="products", lazy="joined")
    category = db.relationship("Category", back_populates="products", lazy="joined")

    variants = db.relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan", lazy="select")
    attributes = db.relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan", lazy="select")
    images = db.relationship("ProductImage", back_populates="product", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        db.Index("idx_products_category", "category_id"),
        db.Index("idx_products_brand", "brand_id"),
        db.Index("idx_products_active", "is_active"),
    )

    def __repr__(self):
        return f"<Product {self.product_name}>"


class ProductVariant(db.Model, TimestampMixin):
    __tablename__ = "product_variants"

    variant_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    variant_name = db.Column(db.String(255))
    size_value = db.Column(db.String(50))
    size_unit = db.Column(db.String(20))
    wholesale_price = db.Column(db.Numeric(15, 2), default=0.00)
    retail_price = db.Column(db.Numeric(15, 2), default=0.00)
    stock_quantity = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)

    product = db.relationship("Product", back_populates="variants", lazy="joined")

    __table_args__ = (
        db.Index("idx_variants_product", "product_id"),
        db.Index("idx_variants_sku", "sku"),
        db.Index("idx_variants_active", "is_active"),
    )

    def __repr__(self):
        return f"<Variant {self.sku} ({self.variant_name})>"


class Attribute(db.Model, TimestampMixin):
    __tablename__ = "attributes"

    attribute_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    attribute_name = db.Column(db.String(100), nullable=False)
    attribute_type = db.Column(db.Enum("text", "number", "boolean", "select", name="attribute_types"), default="text")
    is_filterable = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)

    values = db.relationship("ProductAttribute", back_populates="attribute", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Attribute {self.attribute_name}:{self.attribute_type}>"


class ProductAttribute(db.Model, TimestampMixin):
    __tablename__ = "product_attributes"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    attribute_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("attributes.attribute_id", ondelete="CASCADE"), nullable=False)
    value = db.Column(db.String(255), nullable=False)

    product = db.relationship("Product", back_populates="attributes", lazy="joined")
    attribute = db.relationship("Attribute", back_populates="values", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("product_id", "attribute_id", name="unique_product_attribute"),
        db.Index("idx_product_attrs_product", "product_id"),
        db.Index("idx_product_attrs_attribute", "attribute_id"),
    )

    def __repr__(self):
        return f"<ProductAttribute p:{self.product_id} a:{self.attribute_id} val:{self.value}>"


class ProductImage(db.Model, TimestampMixin):
    __tablename__ = "product_images"

    image_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    
    image_url = db.Column(db.String(500), nullable=False)  # لینک تصویر
    alt_text = db.Column(db.String(500))  # متن جایگزین - بسیار مهم برای سئو تصاویر
    title = db.Column(db.String(300))  # عنوان تصویر (برای tooltip و سئو)
    caption = db.Column(db.Text)  # توضیح زیر تصویر
    sort_order = db.Column(db.Integer, default=0)  # ترتیب نمایش در گالری محصول
    
    is_featured = db.Column(db.Boolean, default=False)  # آیا این تصویر به عنوان تصویر اصلی استفاده شود (در صورت خالی بودن image_url در محصول)

    product = db.relationship("Product", back_populates="images", lazy="joined")

    __table_args__ = (
        db.Index("idx_product_images_product", "product_id"),
        db.Index("idx_product_images_order", "sort_order"),
    )

    def __repr__(self):
        return f"<ProductImage {self.image_id} for Product {self.product_id}>"


class Customer(db.Model, TimestampMixin):
    __tablename__ = "customers"

    customer_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

    orders = db.relationship("Order", back_populates="customer", lazy="select")

    def __repr__(self):
        return f"<Customer {self.email}>"


class Order(db.Model, TimestampMixin):
    __tablename__ = "orders"

    order_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("customers.customer_id"), nullable=False)
    status = db.Column(db.Enum("pending", "confirmed", "shipped", "delivered", "cancelled", name="order_status"), default="pending")
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    customer_notes = db.Column(db.Text)
    order_date = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    customer = db.relationship("Customer", back_populates="orders", lazy="joined")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (db.Index("idx_orders_customer", "customer_id"),)

    def __repr__(self):
        return f"<Order {self.order_number} ({self.status})>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    order_item_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    order_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    variant_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("product_variants.variant_id"), nullable=False)
    product_name = db.Column(db.String(500), nullable=False)
    sku = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(15, 2), nullable=False)

    order = db.relationship("Order", back_populates="items", lazy="joined")
    variant = db.relationship("ProductVariant", lazy="joined")

    __table_args__ = (db.Index("idx_order_items_order", "order_id"),)

    def __repr__(self):
        return f"<OrderItem {self.sku} x{self.quantity}>"


class ArticleCategory(db.Model, TimestampMixin):
    __tablename__ = "article_categories"

    category_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    parent_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("article_categories.category_id", ondelete="SET NULL"), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)  # مهم برای URLهای سئو-فرندلی
    description = db.Column(db.Text)  # توضیح کوتاه برای متا دسکریپشن یا نمایش در لیست دسته‌ها
    image_url = db.Column(db.String(500))  # تصویر نمایه دسته (برای ریچ اسنیپت و جذابیت بصری)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    # رابطه سلسله مراتبی
    parent = db.relationship("ArticleCategory", remote_side=[category_id], backref=backref("children", lazy="select"))
    # رابطه به مقالات
    articles = db.relationship("Article", back_populates="category", lazy="select")

    __table_args__ = (
        db.Index("idx_article_categories_slug", "slug"),
        db.Index("idx_article_categories_active", "is_active"),
    )

    def __repr__(self):
        return f"<ArticleCategory {self.name}>"


class Article(db.Model, TimestampMixin):
    __tablename__ = "articles"

    article_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    category_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("article_categories.category_id"), nullable=False)
    
    title = db.Column(db.String(500), nullable=False)  # عنوان اصلی مقاله - مهم‌ترین فیلد برای سئو
    slug = db.Column(db.String(500), unique=True, nullable=False)  # URL سئو-فرندلی و یکتا
    meta_title = db.Column(db.String(300))  # عنوان متا (می‌تواند متفاوت از title باشد برای بهینه‌سازی بهتر)
    meta_description = db.Column(db.String(500))  # متا دسکریپشن مستقیم برای سئو
    meta_keywords = db.Column(db.Text)  # کلمات کلیدی (هرچند امروزه کمتر استفاده می‌شود اما برخی CMSها هنوز دارند)
    
    short_description = db.Column(db.Text)  # خلاصه کوتاه برای نمایش در لیست مقالات و ریچ اسنیپت
    content = db.Column(db.Text, nullable=False)  # محتوای کامل مقاله (HTML مجاز)
    
    featured_image = db.Column(db.String(500))  # تصویر اصلی مقاله (برای Open Graph و ریچ اسنیپت Article)
    thumbnail_image = db.Column(db.String(500))  # تصویر بند انگشتی برای لیست‌ها
    
    author_name = db.Column(db.String(150))  # نام نویسنده (برای E-A-T گوگل)
    view_count = db.Column(db.Integer, default=0)  # تعداد بازدید (برای مرتب‌سازی محبوب‌ترین‌ها)
    
    is_published = db.Column(db.Boolean, default=False)  # وضعیت انتشار
    published_at = db.Column(db.DateTime, nullable=True)  # تاریخ دقیق انتشار (برای ایندکس بهتر)
    
    is_featured = db.Column(db.Boolean, default=False)  # مقاله ویژه (برای صفحه اصلی)
    is_active = db.Column(db.Boolean, default=True)

    # روابط
    category = db.relationship("ArticleCategory", back_populates="articles", lazy="joined")
    images = db.relationship("ArticleImage", back_populates="article", cascade="all, delete-orphan", lazy="select")
    comments = db.relationship("ArticleComment", back_populates="article", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        db.Index("idx_articles_slug", "slug"),
        db.Index("idx_articles_category", "category_id"),
        db.Index("idx_articles_published", "is_published"),
        db.Index("idx_articles_featured", "is_featured"),
        db.Index("idx_articles_active", "is_active"),
        db.Index("idx_articles_published_at", "published_at"),
    )

    def __repr__(self):
        return f"<Article {self.title}>"
    

class ArticleComment(db.Model, TimestampMixin):
    __tablename__ = "article_comments"

    comment_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    article_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("articles.article_id", ondelete="CASCADE"), nullable=False)
    parent_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("article_comments.comment_id", ondelete="SET NULL"), nullable=True)  # برای پاسخ به کامنت
    
    author_name = db.Column(db.String(150), nullable=False)
    author_email = db.Column(db.String(255), nullable=False)  # برای گراواتار و اطلاع‌رسانی
    author_ip = db.Column(db.String(45))
    content = db.Column(db.Text, nullable=False)
    
    is_approved = db.Column(db.Boolean, default=False)  # بررسی دستی کامنت‌ها
    is_spam = db.Column(db.Boolean, default=False)

    # روابط
    article = db.relationship("Article", back_populates="comments", lazy="joined")
    parent = db.relationship("ArticleComment", remote_side=[comment_id], backref=backref("replies", lazy="select"))

    __table_args__ = (
        db.Index("idx_comments_article", "article_id"),
        db.Index("idx_comments_parent", "parent_id"),
        db.Index("idx_comments_approved", "is_approved"),
    )

    def __repr__(self):
        return f"<ArticleComment {self.comment_id} on Article {self.article_id}>"


class ArticleImage(db.Model, TimestampMixin):
    __tablename__ = "article_images"

    image_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    article_id = db.Column(BIGINT(unsigned=True), db.ForeignKey("articles.article_id", ondelete="CASCADE"), nullable=False)
    
    image_url = db.Column(db.String(500), nullable=False)  # لینک تصویر
    alt_text = db.Column(db.String(500))  # متن جایگزین - بسیار مهم برای سئو تصاویر
    title = db.Column(db.String(300))  # عنوان تصویر (برای tooltip و سئو)
    caption = db.Column(db.Text)  # توضیح زیر تصویر
    sort_order = db.Column(db.Integer, default=0)  # ترتیب نمایش در گالری مقاله
    
    is_featured = db.Column(db.Boolean, default=False)  # آیا این تصویر به عنوان تصویر اصلی استفاده شود (در صورت خالی بودن featured_image)

    article = db.relationship("Article", back_populates="images", lazy="joined")

    __table_args__ = (
        db.Index("idx_article_images_article", "article_id"),
        db.Index("idx_article_images_order", "sort_order"),
    )

    def __repr__(self):
        return f"<ArticleImage {self.image_id} for Article {self.article_id}>"


class ContactMessage(db.Model, TimestampMixin):
    __tablename__ = "contact_messages"

    message_id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    name = db.Column(db.String(255))
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255))
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text)
    is_responded = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)

    def __repr__(self):
        return f"<ContactMessage {self.message_id} from {self.name}>"


class SiteSetting(db.Model, TimestampMixin):
    __tablename__ = "site_settings"

    key = db.Column(db.String(255), primary_key=True)
    value = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<SiteSetting {self.key}>"