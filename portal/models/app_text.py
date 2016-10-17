"""Model classes for app_text

Customizing the templates for application specific needs can be done
at several levels.  This module houses tables used to generate
app specific strings.  Values are imported and exported through the
SitePersistence mechanism, and looked up in a template using the
`app_text(string)` method.

"""
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

    NB javascript variables are not evaluated till the client browser sees
    the page, therefore any javascript variables will not be available in time
    for app_text() to use them.

    """
    item = AppText.query.filter_by(name=name).first()
    if not item:
        raise ValueError("unknown customized app string '{}'".format(name))

    text = str(item)
    try:
        return text.format(*args)
    except IndexError as err:
        if not args:
            args = ('<None>',)
        raise ValueError(
            "AppText with name '{}' defines more parameters "
            "than provided: `{}`".format(name, *args))
