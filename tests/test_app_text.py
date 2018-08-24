"""Unit test module for app_text"""
from __future__ import unicode_literals  # isort:skip
from future import standard_library  # isort:skip

standard_library.install_aliases()  # noqa: E402

import sys
from urllib.parse import parse_qsl, unquote_plus, urlparse

from flask import render_template_string
from flask_webtest import SessionScope
import pytest

from portal.extensions import db
from portal.models.app_text import (
    AppText,
    MailResource,
    UnversionedResource,
    VersionedResource,
    app_text,
)
from portal.models.user import User
from tests import TEST_USER_ID, TestCase


class Url(object):
    '''A url object that can be compared with other url orbjects
    without regard to the vagaries of encoding, escaping, and ordering
    of parameters in query strings.'''

    def __init__(self, url):
        parts = urlparse(url)
        _query = frozenset(parse_qsl(parts.query))
        _path = unquote_plus(parts.path)
        parts = parts._replace(query=_query, path=_path)
        self.parts = parts

    def __eq__(self, other):
        return self.parts == other.parts

    def __hash__(self): return hash(self.parts)


class TestAppText(TestCase):

    def test_expansion(self):
        with SessionScope(db):
            title = AppText(name='landing title')
            title.custom_text = '_expanded_'
            db.session.add(title)
            db.session.commit()
        result = render_template_string(
            '<html></head><body>{{ app_text("landing title") }}<body/><html/>')
        assert '_expanded_' in result

    def test_missing_arg(self):
        with SessionScope(db):
            title = AppText(name='landing title')
            title.custom_text = '_expanded_ {0}'
            db.session.add(title)
            db.session.commit()
        with pytest.raises(ValueError):
            render_template_string('<html></head><body>'
                                   '{{ app_text("landing title") }}'
                                   '<body/><html/>')

    def test_permanent_url(self):
        args = {
            'uuid': 'cbe17d0d-f25d-27fb-0d92-c22bc687bb0f',
            'origin': self.app.config['LR_ORIGIN'],
            'version': '1.3'}
        sample = (
            '{origin}/c/portal/truenth/asset/detailed?'
            'uuid={uuid}&version=latest'.format(**args))
        expected = (
            '{origin}/c/portal/truenth/asset?uuid={uuid}&'
            'version={version}'.format(**args))

        result = VersionedResource(sample, locale_code='en_AU')._permanent_url(
            generic_url=sample, version=args['version'])
        assert Url(result) == Url(expected)

    def test_config_value_in_custom_text(self):
        self.app.config['CT_TEST'] = 'found!'
        with SessionScope(db):
            embed_config_value = AppText(
                name='embed config value',
                custom_text='Do you see {config[CT_TEST]}?')
            db.session.add(embed_config_value)
            db.session.commit()

        result = app_text('embed config value')
        assert 'found!' in result

    def test_fetch_elements_invalid_url(self):
        sample_url = "https://notarealwebsitebeepboop.com"
        sample_error = (
            "Could not retrieve remove content - Server could not be reached")
        result = VersionedResource(sample_url, locale_code=None)
        assert result.error_msg == sample_error
        assert result.url == sample_url
        assert result.asset == sample_error

    def test_asset_variable_replacement(self):
        test_user = User.query.get(TEST_USER_ID)

        test_url = "https://notarealwebsitebeepboop.com"
        test_asset = "Hello {firstname} {lastname}! Your user ID is {id}"
        test_vars = {"firstname": test_user.first_name,
                     "lastname": test_user.last_name,
                     "id": TEST_USER_ID}
        resource = UnversionedResource(test_url,
                                       asset=test_asset,
                                       variables=test_vars)
        rf_id = int(resource.asset.split()[-1])
        assert rf_id == TEST_USER_ID

        invalid_asset = "Not a real {variable}!"
        resource = UnversionedResource(test_url,
                                       asset=invalid_asset,
                                       variables=test_vars)
        error_key = resource.asset.split()[-1]
        if sys.version_info[0] < 3:
            assert error_key == "u'variable'"
        else:
            assert error_key == "'variable'"

    def test_mail_resource(self):
        testvars = {"subjkey": "test",
                    "bodykey1": '\u2713',
                    "bodykey2": "456",
                    "footerkey": "foot"}
        tmr = MailResource(None, locale_code='en_AU', variables=testvars)

        assert tmr.subject == "TESTING SUBJECT"
        assert tmr.body.splitlines()[0] == "TESTING BODY"
        assert tmr.body.splitlines()[1] == "TESTING FOOTER"

        tmr._subject = "Replace this: {subjkey}"
        tmr._body = "Replace these: {bodykey1} and {bodykey2}"
        tmr._footer = "Replace this: {footerkey}"

        assert tmr.subject.split()[-1] == "test"
        assert tmr.body.splitlines()[0].split()[-1] == "456"
        assert tmr.body.splitlines()[1].split()[-1] == "foot"
        assert set(tmr.variable_list) == set(testvars.keys())
        assert testvars['bodykey1'] in tmr.body

        # test footer optionality
        tmr._footer = None
        assert len(tmr.body.splitlines()) == 1
