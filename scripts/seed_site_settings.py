from app import app
from extensions import db
from models import SiteSetting

# Defaults extracted from templates/base.html
DEFAULTS = {
    'logo_text': 'شوفاژ حیدری',
    'ticker_items': '\n'.join([
        'واتساپ: 0912 926 5458',
        'ارسال رایگان تهران و کرج',
        'نصب حرفه‌ای پکیج و رادیاتور',
        'ضمانت اصالت کالا',
        'مشاوره رایگان تأسیسات',
    ]),
    'footer_about': 'تأمین کننده تجهیزات تأسیلات ساختمان با بهترین قیمت و ضمانت اصالت',
    'contact_phone': '021-55661234',
    'contact_mobile': '09121234567',
}

if __name__ == '__main__':
    with app.app_context():
        created = []
        for k, v in DEFAULTS.items():
            s = SiteSetting.query.get(k)
            if s is None:
                s = SiteSetting(key=k, value=v)
                db.session.add(s)
                created.append(k)
        if created:
            db.session.commit()
            print('Created settings:', ', '.join(created))
        else:
            print('No new settings needed.')
