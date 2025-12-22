"""
Seed the database with sample HVAC ecommerce data.

Usage:
    export DATABASE_URL="mysql+pymysql://hvac_user:123456@127.0.0.1/hvac_ecommerce"
    python seed_sample_data.py
"""

import os
from contextlib import contextmanager

# Set DATABASE_URL BEFORE importing app
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("Please set DATABASE_URL environment variable.")

os.environ["DATABASE_URL"] = database_url

from app import app
from extensions import db
from models import (
    Vendor, Brand, Category, Attribute,
    Product, ProductVariant, ProductAttribute,
    ArticleCategory
)


@contextmanager
def no_autoflush(session):
    """Temporarily disable autoflush to avoid premature INSERTs."""
    try:
        session.autoflush = False
        yield
    finally:
        session.autoflush = True


def get_or_create(session, model, defaults=None, **kwargs):
    """Get existing instance or create a new one (safe with no_autoflush)."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance

    params = kwargs.copy()
    if defaults:
        params.update(defaults)

    instance = model(**params)
    session.add(instance)
    return instance


def seed():
    # Override config to ensure we're using the right database
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    print(f"🔗 Connecting to: {database_url}")
    print(f"📊 Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")

    with app.app_context():
        session = db.session
        
        # Verify we're using MySQL - use db.engine instead of session.bind
        engine_name = db.engine.dialect.name
        print(f"✓ Database engine: {engine_name}")
        if engine_name == 'sqlite':
            raise RuntimeError("❌ Still connected to SQLite! Check your app.py configuration.")

        # 1. Create Vendor and commit immediately (so it gets vendor_id)
        vendor = get_or_create(
            session,
            Vendor,
            vendor_name="شوفاژ حیدری",
            defaults={"phone": "02144332211", "is_active": True}
        )
        session.commit()  # Critical: commit now to assign vendor_id
        print(f"✓ Created vendor with ID: {vendor.vendor_id}")

        # 2. All subsequent queries inside no_autoflush to avoid autoflush issues
        with no_autoflush(session):
            # Brands
            brand_names = ["بوتان", "ایران رادیاتور", "ایساتیس", "لورچ", "افروز"]
            brands = []
            for name in brand_names:
                brand = get_or_create(session, Brand, brand_name=name)
                brands.append(brand)
            # Ensure brands have IDs before referencing them later
            session.commit()
            print(f"✓ Created {len(brands)} brands")

            # Categories
            radiators = get_or_create(
                session,
                Category,
                category_name="رادیاتورها",
                slug="radiators"
            )

            boilers = get_or_create(session, Category, category_name="پکیج ها", slug="boilers")
            pipes = get_or_create(session, Category, category_name="لوله و اتصالات", slug="pipes")

            aluminum = get_or_create(
                session,
                Category,
                category_name="رادیاتور آلومینیومی",
                slug="aluminum-radiators",
                defaults={"parent_id": radiators.category_id}
            )

            get_or_create(
                session,
                Category,
                category_name="حوله خشک کن",
                slug="towel-warmers",
                defaults={"parent_id": radiators.category_id}
            )
            # Commit categories so their IDs are available
            session.commit()
            print("✓ Created categories")

            # Attributes
            attributes_data = [
                ("جنس بدنه", "text", True, 1),
                ("تعداد پره", "number", True, 2),
                ("راندمان", "number", True, 3),
                ("وزن", "number", False, 4),
                ("گارانتی", "text", False, 5),
                ("قدرت گرمایی", "number", True, 6),
            ]

            for name, attr_type, is_filterable, order in attributes_data:
                get_or_create(
                    session,
                    Attribute,
                    attribute_name=name,
                    defaults={
                        "attribute_type": attr_type,
                        "is_filterable": is_filterable,
                        "display_order": order
                    }
                )
            print("✓ Created attributes")

            # Sample Product
            product = get_or_create(
                session,
                Product,
                slug="radiator-isatis",
                defaults={
                    "vendor_id": vendor.vendor_id,
                    "brand_id": brands[2].brand_id,  # ایساتیس
                    "category_id": aluminum.category_id,
                    "product_name": "رادیاتور ایساتیس",
                    "description": "رادیاتور آلومینیومی ایساتیس با کیفیت بالا"
                }
            )
            # Ensure product has an ID so variants can reference it
            session.commit()
            print("✓ Created product")

            # Product Variants
            variants_data = [
                ("ISATIS-60", "60 سانتی متر", "60", "cm", 29_500_000, 10),
                ("ISATIS-80", "80 سانتی متر", "80", "cm", 29_500_000, 8),
                ("ISATIS-100", "100 سانتی متر", "100", "cm", 29_500_000, 5),
                ("ISATIS-120", "120 سانتی متر", "120", "cm", 29_500_000, 12),
                ("ISATIS-140", "140 سانتی متر", "140", "cm", 29_500_000, 7),
                ("ISATIS-160", "160 سانتی متر", "160", "cm", 29_500_000, 4),
            ]

            for sku, name, size_val, unit, price, stock in variants_data:
                get_or_create(
                    session,
                    ProductVariant,
                    sku=sku,
                    defaults={
                        "product_id": product.product_id,
                        "variant_name": name,
                        "size_value": size_val,
                        "size_unit": unit,
                        "retail_price": price,
                        "stock_quantity": stock
                    }
                )
            print(f"✓ Created {len(variants_data)} product variants")

            # Product Attributes
            product_attrs = {
                "جنس بدنه": "آلومینیوم",
                "تعداد پره": "10",
                "راندمان": "92",
                "وزن": "3.5",
                "گارانتی": "5 سال",
            }

            for attr_name, value in product_attrs.items():
                attr = session.query(Attribute).filter_by(attribute_name=attr_name).one_or_none()
                if attr:
                    get_or_create(
                        session,
                        ProductAttribute,
                        product_id=product.product_id,
                        attribute_id=attr.attribute_id,
                        defaults={"value": value}
                    )
            print("✓ Created product attributes")

        # Final commit for everything else
        session.commit()
        print("✅ Sample data seeded successfully! Everything is in the database now.")

        # ==================== Article Categories ====================
        print("🌱 Seeding Article Categories...")
        # والد اول: آخرین مقالات و راهنماها
        guides_parent = get_or_create(
            session,
            ArticleCategory,
            slug="latest-articles-guides",
            defaults={
                "name": "آخرین مقالات و راهنماها",
                "description": "مجموعه مقالات آموزشی، راهنمای خرید و نگهداری تجهیزات گرمایشی",
                "is_active": True,
                "sort_order": 10
            }
        )
        # فرزند آن
        get_or_create(
            session,
            ArticleCategory,
            slug="package-selection-maintenance",
            defaults={
                "name": "راهنمای انتخاب پکیج، نگهداری رادیاتور و مطالب تخصصی تأسیساتی",
                "description": "راهنماهای جامع خرید پکیج، نگهداری رادیاتور و نکات فنی تأسیسات",
                "parent_id": guides_parent.category_id,
                "is_active": True,
                "sort_order": 1
            }
        )
        # والد دوم: اخبار و اطلاعیه‌ها
        news_parent = get_or_create(
            session,
            ArticleCategory,
            slug="news-announcements",
            defaults={
                "name": "اخبار و اطلاعیه‌ها",
                "description": "آخرین اخبار صنعت گرمایش، به‌روزرسانی محصولات و اطلاعیه‌های فروشگاه",
                "is_active": True,
                "sort_order": 20
            }
        )
        # فرزند آن
        get_or_create(
            session,
            ArticleCategory,
            slug="discounts-stock-updates",
            defaults={
                "name": "اطلاع‌رسانی تخفیف‌ها و موجودی محصولات",
                "description": "اعلام تخفیف‌های ویژه، موجود شدن مجدد محصولات و پیشنهادات محدود",
                "parent_id": news_parent.category_id,
                "is_active": True,
                "sort_order": 1
            }
        )
        # والد سوم: جزئیات محصول نمونه
        product_details_parent = get_or_create(
            session,
            ArticleCategory,
            slug="sample-product-details",
            defaults={
                "name": "جزئیات محصول نمونه",
                "description": "بررسی کامل و مشخصات فنی یک محصول نمونه به عنوان الگو",
                "is_active": True,
                "sort_order": 30
            }
        )
        # فرزند آن
        get_or_create(
            session,
            ArticleCategory,
            slug="sample-product-full-specs",
            defaults={
                "name": "مشاهده صفحه محصول نمونه و مشخصات کامل",
                "description": "نمایش کامل مشخصات، تصاویر، ویژگی‌ها و نظرات یک محصول نمونه",
                "parent_id": product_details_parent.category_id,
                "is_active": True,
                "sort_order": 1
            }
        )
        print("✓ Article categories seeded successfully with hierarchy")


if __name__ == "__main__":
    seed()