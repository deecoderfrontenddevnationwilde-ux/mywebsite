"""
Shared extension instances.

Kept in their own module (rather than created inside app.py) so that
models/ and routes/ can import `db` without causing circular imports.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
