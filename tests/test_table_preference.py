"""Unit test module for table preferences logic"""
from __future__ import unicode_literals  # isort:skip

import json

from flask_webtest import SessionScope

from portal.extensions import db
from portal.models.table_preference import TablePreference
from tests import TEST_USER_ID, TestCase


class TestTablePreference(TestCase):
    """Table Preference tests"""

    def test_preference_upsert(self):
        self.login()

        filter_json = {"field1": "filter1", "field2": "filter2"}
        data = {"sort_field": "testSort",
                "sort_order": "asc",
                "filters": filter_json}
        resp = self.client.post(
            '/api/user/{}/table_preferences/testTable'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))

        assert resp.status_code == 200
        assert resp.json['user_id'] == TEST_USER_ID

        pref = TablePreference.query.filter_by(user_id=TEST_USER_ID,
                                               table_name='testTable').first()

        first_update_id = pref.id
        first_update_at = pref.updated_at
        assert first_update_at
        assert pref.filters == filter_json
        assert pref.sort_order == "asc"

        # test that updates work, and ONLY update the provided field(s)
        data = {"sort_order": "desc"}
        resp2 = self.client.post(
            '/api/user/{}/table_preferences/testTable'.format(TEST_USER_ID),
            content_type='application/json',
            data=json.dumps(data))

        assert resp2.status_code == 200
        assert resp2.json['id'] == first_update_id

        pref = TablePreference.query.filter_by(user_id=TEST_USER_ID,
                                               table_name='testTable').first()

        assert pref.updated_at != first_update_at
        assert pref.filters == filter_json
        assert pref.sort_order == "desc"

    def test_preference_get(self):
        self.login()

        filter_json = {"field1": "filter1", "field2": "filter2"}
        pref = TablePreference(user_id=TEST_USER_ID,
                               table_name="testTable",
                               sort_field="testSort",
                               sort_order="desc",
                               filters=filter_json)
        with SessionScope(db):
            db.session.add(pref)
            db.session.commit()

        resp = self.client.get('/api/user/{}/table_preferences/'
                               'testTable'.format(TEST_USER_ID))

        assert resp.status_code == 200
        assert resp.json['user_id'] == TEST_USER_ID
        assert resp.json['filters'] == filter_json

    def test_no_preferences(self):
        self.login()
        # Prior to saving prefs, should just get a valid empty
        resp = self.client.get('/api/user/{}/table_preferences/'
                               'testTable'.format(TEST_USER_ID))

        assert resp.status_code == 200
        assert resp.json == {}
