""" model data for adherence reports """
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
import re

from ..database import db
withdrawn = " post-withdrawn"

class AdherenceData(db.Model):
    """ Cached adherence report data

    Full history adherence data is expensive to generate, retain between reports.
    Cache reportable data in simple JSON structure, maintaining keys for lookup
    and invalidation timestamps.

    rs_id_visit: the numeric rs_id and visit month string joined with a colon
    valid_till: old history data never changes, unless an external event such
        as a user's consent date or organization research protocol undergoes
        change.  active visits require more frequent updates but are considered
        fresh enough for days.  client code sets valid_till as appropriate.

    """
    __tablename__ = 'adherence_data'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.ForeignKey('users.id'), index=True, nullable=False)
    rs_id_visit = db.Column(
        db.Text, index=True, nullable=False,
        doc="rs_id:visit_name")
    valid_till = db.Column(
        db.DateTime, nullable=False, index=True,
        doc="cached values good till time passed")
    data = db.Column(JSONB)

    __table_args__ = (UniqueConstraint(
        'patient_id', 'rs_id_visit', name='_adherence_unique_patient_visit'),)

    @staticmethod
    def rs_visit_string(rs_id, visit_string, post_withdrawn=False):
        """trivial helper to build rs_id_visit string into desired format"""
        assert isinstance(rs_id, int)
        assert visit_string
        if post_withdrawn:
            visit_string += withdrawn
        return f"{rs_id}:{visit_string}"

    def rs_visit_parse(self):
        """break parts of rs_id and visit_string out of rs_id_visit field"""
        rs_id, visit_string = self.rs_id_visit.split(':')
        assert visit_string
        if visit_string.endswith(withdrawn):
            visit_string = visit_string[:-(len(withdrawn))]
        return int(rs_id), visit_string

    @staticmethod
    def fetch(patient_id, rs_id_visit):
        """shortcut for common lookup need

        :return: populated AdherenceData instance if found, None otherwise
        """
        result = AdherenceData.query.filter(
            AdherenceData.patient_id == patient_id).filter(
            AdherenceData.rs_id_visit == rs_id_visit).first()
        if result:
            assert result.valid_till > datetime.utcnow()
        return result

    @staticmethod
    def persist(patient_id, rs_id_visit, valid_for_days, data):
        """shortcut to persist a row, returns new instance"""
        import json
        valid_till = datetime.utcnow() + timedelta(days=valid_for_days)
        for k, v in data.items():
            try:
                json.dumps(k)
                json.dumps(v)
            except TypeError:
                raise ValueError(f"couldn't encode {k}:{v}, {type(v)}")

        record = AdherenceData(
            patient_id=patient_id,
            rs_id_visit=rs_id_visit,
            valid_till=valid_till,
            data=data)
        db.session.add(record)
        db.session.commit()
        return db.session.merge(record)


def sort_by_visit_key(d):
    """Given dict returns ordered list of values sorted by key

    Sort by key using the following rules:
    "Baseline" comes first
    "Indefinite" comes last
    "Month <n>" in the middle, sorted by integer value

    :returns: list of values sorted by keys
    """
    pattern = re.compile(f"Month ([0-9]+)({withdrawn})?")
    def sort_key(key):
        if key == 'Baseline':
            return 0, 0
        elif key == f"Baseline{withdrawn}":
            return 0, 1
        elif key == 'Indefinite':
            return 2, 0
        elif key == f'Indefinite{withdrawn}':
            return 2, 1
        else:
            match = pattern.match(key)
            if not match.groups():
                raise ValueError(f"couldn't parse key {key}")
            month_num = int(match.groups()[0])
            if match.groups()[1]:
                month_num += 100
            return 1, month_num

    sorted_keys = sorted(d.keys(), key=sort_key)
    sorted_values = [d[key] for key in sorted_keys]
    return sorted_values


def sorted_adherence_data(patient_id, research_study_id):
    """Shortcut to obtain ordered list for given patient:research_study"""
    rows = AdherenceData.query.filter(
        AdherenceData.patient_id == patient_id).filter(
        AdherenceData.rs_id_visit.like(f"{research_study_id}%"))
    # Sort locally, given complicated sort function
    presorted = {row.rs_id_visit.split(':')[1]: row.data for row in rows}
    return sort_by_visit_key(presorted)
