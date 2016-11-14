"""Unit test module for app_text"""
from flask import render_template
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.app_text import AppText, ConsentATMA
from tests import TestCase


class TestAppText(TestCase):

    def test_expansion(self):
        with SessionScope(db):
            title = AppText.query.filter_by(name='landing title').one()
            title.custom_text = '_expanded_'
            db.session.commit()
        result = render_template('landing.html')
        self.assertTrue('_expanded_' in result)

    def test_missing_arg(self):
        with SessionScope(db):
            title = AppText.query.filter_by(name='landing title').one()
            title.custom_text = '_expanded_ {0}'
            db.session.commit()
        self.assertRaises(ValueError, render_template, 'landing.html')

    def test_permanent_url(self):
        sample = 'https://stg-lr7.us.truenth.org/c/portal/truenth/asset/detailed?groupId=20147&articleId=52668'
        version = '1.3'
        locale = 'en_AU'
        expected = 'https://stg-lr7.us.truenth.org/c/portal/truenth/asset?groupId=20147&articleId=52668&version=1.3&languageId=en_AU'

        result = ConsentATMA.permanent_url(generic_url=sample, version=version, languageId=locale)
        self.assertEquals(result, expected)
