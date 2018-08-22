"""User Document module"""
from datetime import datetime
import os
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from ..database import db
from ..date_tools import FHIR_datetime
from .intervention import Intervention
from .user import User


class UserDocument(db.Model):
    """ORM class for user document upload data

    Capture and store uploaded user documents
    (e.g. patient reports, user avatar images, etc).

    """
    __tablename__ = 'user_documents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False)
    document_type = db.Column(db.Text, nullable=False)
    filename = db.Column(db.Text, nullable=False)
    filetype = db.Column(db.Text, nullable=False)
    uuid = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False)
    intervention_id = db.Column(
        db.ForeignKey('interventions.id'), nullable=True)

    intervention = db.relationship('Intervention')

    def __str__(self):
        return self.filename

    def as_json(self):
        d = {}
        d['id'] = self.id
        d['user_id'] = self.user_id
        d['document_type'] = self.document_type
        d['uploaded_at'] = FHIR_datetime.as_fhir(self.uploaded_at)
        d['filename'] = self.filename
        d['filetype'] = self.filetype
        if self.intervention:
            d['contributor'] = self.intervention.description

        return d

    @classmethod
    def from_post(cls, upload_file, data):
        user = User.query.get(data['user_id'])
        if not user:
            raise ValueError("user not found")
        if not data['document_type']:
            raise ValueError('must provide document type')
        if not (upload_file.filename and upload_file.filename.strip()):
            raise ValueError("invalid filename")
        filename = secure_filename(upload_file.filename)
        filetype = filename.rsplit('.', 1)[1]
        if filetype.lower() not in data['allowed_extensions']:
            raise ValueError("filetype must be one of: " + ", ".join(
                data['allowed_extensions']))
        file_uuid = uuid4()
        try:
            upload_dir = os.path.join(
                current_app.root_path,
                current_app.config.get("FILE_UPLOAD_DIR"),
            )
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)
            upload_file.save(os.path.join(upload_dir, str(file_uuid)))
        except:
            raise OSError("could not save file")
        if 'contributor' in data:
            interv = Intervention.query.filter_by(
                description=data['contributor']).first()

        return cls(user_id=data['user_id'],
                   document_type=data['document_type'],
                   filename=filename,
                   filetype=filetype,
                   uuid=file_uuid,
                   uploaded_at=datetime.utcnow(),
                   intervention=interv
                   )

    def get_file_contents(self):
        filepath = os.path.join(
            current_app.root_path,
            current_app.config.get("FILE_UPLOAD_DIR"),
            self.uuid,
        )
        if not os.path.exists(filepath):
            raise ValueError("could not find file")
        try:
            with open(filepath, "r") as file_in:
                file_contents = file_in.read()
        except:
            raise ValueError("could not open file")

        return file_contents
