"""Database inclusion hook - keep minimal to avoid cyclic dependencies"""

# SQLAlchemy provides the database object relational mapping (ORM)
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
