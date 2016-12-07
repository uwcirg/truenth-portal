"""Unit test module for app_text"""
from flask import render_template
from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.app_text import AppText, ConsentATMA, app_text
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
        expected = 'https://stg-lr7.us.truenth.org/c/portal/truenth/asset?groupId=20147&articleId=52668&version=1.3'

        result = ConsentATMA.permanent_url(generic_url=sample, version=version)
        self.assertEquals(result, expected)

    def test_config_value_in_custom_text(self):
        self.app.application.config['CT_TEST'] = 'found!'
        with SessionScope(db):
            embed_config_value = AppText(
                name='embed config value',
                custom_text='Do you see {config[CT_TEST]}?')
            db.session.add(embed_config_value)
            db.session.commit()

        result = app_text('embed config value')
        self.assertTrue('found!' in result)

