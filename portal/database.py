"""Database inclusion hook - keep minimal to avoid cyclic dependencies"""

# SQLAlchemy provides the database object relational mapping (ORM)
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy_caching import CachingQuery

# Test theory, that the coupling of redis to sql is what causes
# unittests to become deadlocked when trying to drop all tables
#db = SQLAlchemy(query_class=CachingQuery)
db = SQLAlchemy()
