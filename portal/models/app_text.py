"""Model classes for app_text

Customizing the templates for application specific needs can be done
at several levels.  This module houses tables used to generate
app specific strings.  Values are imported and exported through the
SitePersistence mechanism, and looked up in a template using the
`app_text(string)` method.

"""
from abc import ABCMeta, abstractmethod
from flask import current_app
from flask_babel import gettext
import requests
from urllib import urlencode
from urlparse import parse_qsl, urlparse

from ..extensions import db


class AppText(db.Model):
    """Model representing application specific strings for customization

    The portal (shared services) can be configured to support a number
    of specific sites.  This class provides a mechanism to store and lookup
    any text string needing to be customized.

    """
    __tablename__ = 'apptext'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)
    custom_text = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return "{} ({}, {})".format(self.__class__.__name__,
                                    self.name, str(self))

    def __str__(self):
        if self.custom_text:
            return self.custom_text
        return self.text

    def __unicode__(self):
        if self.custom_text:
            return self.custom_text
        return self.text

    @classmethod
    def from_json(cls, data):
        if 'name' not in data:
            raise ValueError("missing required 'name' field")
        app_text = AppText.query.filter_by(name=data['name']).first()
        if not app_text:
            app_text = cls()
            app_text.name = data['name']
            app_text.custom_text = data.get('custom_text')
            db.session.add(app_text)
        else:
            app_text.custom_text = data.get('custom_text')
        return app_text

    def as_json(self):
        d = {}
        d['resourceType'] = 'AppText'
        d['name'] = self.name
        if self.custom_text:
            d['custom_text'] = self.custom_text
        return d


class AppTextModelAdapter(object):
    """Several special purpose patterns used for lookups

    Make access consistent and easy for model classes where appropriate

    Abstract base class - defining methods each model adapter needs
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def name_key(**kwargs):
        """Return the named key as used by AppText for the type"""
        raise NotImplemented


class ConsentATMA(AppTextModelAdapter):
    """AppTextModelAdapter for Consent agreements - namely the URL per org"""

    @staticmethod
    def name_key(**kwargs):
        """Generate AppText name key for a consent agreement

        :param organization: for which the consent agreement applies
        :returns: string for AppText.name field

        """
        organization = kwargs.get('organization')
        if not organization:
            raise ValueError("required organization parameter not defined")
        return "{} organization consent URL".format(organization.name)


class ToU_ATMA(AppTextModelAdapter):
    """AppTextModelAdapter for Terms Of Use agreements - namely the URL"""

    @staticmethod
    def name_key(**kwargs):
        """Generate AppText name key for a Terms of Use agreement

        Not expecting any args at this time - may specialize per study
        or organization in the future as needed.

        :returns: string for AppText.name field

        """
        return "Terms of Use URL"


class AboutATMA(AppTextModelAdapter):
    """AppTextModelAdapter for `About` - namely the URL"""

    @staticmethod
    def name_key(**kwargs):
        """Generate AppText name key for `about` URL

        :param subject: required subject, i.e. 'TrueNTH' or 'Movember'
        :returns: string for AppText.name field

        """
        if not kwargs.get('subject'):
            raise ValueError("required 'subject' parameter not defined")
        return "About {} URL".format(kwargs.get('subject'))


class LegalATMA(AppTextModelAdapter):
    """AppTextModelAdapter for Legal - namely the URL"""

    @staticmethod
    def name_key(**kwargs):
        """Generate AppText name key for legal URL

        :returns: string for AppText.name field

        """
        return "Legal URL"


class VersionedResource(object):
    """Helper to manage versioned resource URLs (typically on Liferay)"""

    @staticmethod
    def permanent_url(generic_url, version):
        """Produce a permanent url from the metadata provided

        Resources are versioned - but the link maintained in the app_text
        table is not.

        When requesting the detailed resource, the effective version number is
        returned.  This method returns a permanent URL including the version
        number, useful for audit and tracking information.

        """
        parsed = urlparse(generic_url)
        qs = dict(parse_qsl(parsed.query))
        qs['version'] = version

        path = parsed.path
        if path.endswith('/detailed'):
            path = path[:-(len('/detailed'))]
        format_dict = {
            'scheme': parsed.scheme,
            'netloc': parsed.netloc,
            'path': path,
            'qs': urlencode(qs)}
        url = "{scheme}://{netloc}{path}?{qs}".format(**format_dict)
        return url


    @staticmethod
    def fetch_elements(url):
        """Given a URL, fetch the asset and permanent version of URL

        Pulls and returns the 'asset' (i.e. response.text) from the given URL.
        If version info is provided in the `detailed` response, a permanent
        version of the URL is also returned.

        :param url: the URL to pull details and asset from
        :returns: (asset, url)

        """
        response = requests.get(url)
        try:
            return (
                response.json()['asset'],
                VersionedResource.permanent_url(
                    version=response.json()['version'],
                    generic_url=url))
        except ValueError:  # thrown when no json is available in response
            return (response.text, url)

def app_text(name, *args):
    """Look up and return cusomized application text string

    May be embedded directly in jinja2 templates.  Call `app_text()`
    with the 'name' to uniquely identify the custom string to lookup
    and return.

    Custom strings may contain an arbitrary number of additional parameters.
    They should be embedded as zero indexed curly brackets for inclusion.

    For example, given AppText(name='ex', custom_text='Hello {0}. {1} {0}'), a
    call to `app_text('ex', 'Bob', 'Gooday')` would return:
        'Hello Bob. Gooday Bob'

    Custom strings may also reference configuration variables.  For example,
    to include the configured value of USER_APP_NAME in the custom_text,
    given:
        AppText(name='config example',
                custom_text='Welcome to {config[USER_APP_NAME]}")

    a call to `app_text('config example')` would produce something like:
        'Welcome to TrueNTH'

    NB javascript variables are not evaluated till the client browser sees
    the page, therefore any javascript variables will not be available in time
    for app_text() to use them.

    """
    item = AppText.query.filter_by(name=name).first()
    if not item:
        raise ValueError("unknown customized app string '{}'".format(name))

    text = str(item)
    try:
        if 'config[' in text:
            return gettext(text.format(*args, config=current_app.config))
        return gettext(text.format(*args))
    except IndexError:
        if not args:
            args = ('<None>',)
        raise ValueError(
            "AppText with name '{}' defines more parameters "
            "than provided: `{}`".format(name, *args))
