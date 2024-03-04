"""Database inclusion hook - keep minimal to avoid cyclic dependencies"""

# SQLAlchemy provides the database object relational mapping (ORM)
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy_caching import CachingQuery

db = SQLAlchemy(query_class=CachingQuery)
