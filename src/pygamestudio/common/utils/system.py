import locale


def get_system_lang():
    lang, encoding = locale.getdefaultlocale()
    if lang == 'zh_CN':
        return lang
    else:
        return 'en'
