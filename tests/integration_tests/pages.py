from page_objects import PageElement, PageObject


class LoginPage(PageObject):
    username = PageElement(name='email')
    password = PageElement(name='password')
    login_button = PageElement(css='input[type="submit"]')
    facebook_button = PageElement(css='.btn-facebook')
