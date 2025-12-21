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
    description = db.Column(db.Text)
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
