import os
import gettext
import locale

class I18nManager:
    def __init__(self, domain='messages', locale_dir='locales', default_lang='en'):
        self.domain, self.locale_dir, self.default_lang = domain, locale_dir, default_lang
        self.current_lang, self.translator = default_lang, None
        
        os.makedirs(locale_dir, exist_ok=True)
        self.set_language(self._detect_system_language())
    
    def _detect_system_language(self):
        try:
            sys_locale = locale.getdefaultlocale()[0]
            return 'zh' if sys_locale and sys_locale.startswith('zh') else 'en' if sys_locale and sys_locale.startswith('en') else self.default_lang
        except:
            return self.default_lang
    
    def set_language(self, lang_code):
        self.current_lang = lang_code
        try:
            self.translator = gettext.translation(self.domain, localedir=self.locale_dir, languages=[lang_code])
        except FileNotFoundError:
            self.translator = gettext.NullTranslations()
    
    def get_text(self, msg):
        return self.translator.gettext(msg) if self.translator else msg
    
    def nget_text(self, singular, plural, n):
        return self.translator.ngettext(singular, plural, n) if self.translator else (singular if n == 1 else plural)

i18n = I18nManager()

def _(msg): return i18n.get_text(msg)
def ngettext(singular, plural, n): return i18n.nget_text(singular, plural, n)
def set_language(lang): i18n.set_language(lang)
def get_current_language(): return i18n.current_lang
