# package-overview
Package build overview and FTBFS tracking across multiple koji instances.

# Requirements

- fedmsg
- koji
- python-flask
- python-flask-sqlalchemy
- database supported by sqlalchemy(most basic and easy to setup is sqlite, but not recommended for production)

# Initialization

- Setup database in statusweb.py script.(for sqlite set SQLALCHEMY_DATABASE_URI to "sqlite:///database.db")
- Run initdb.py script.
- To run web without httpd(for development only!!!), just run statusweb.py. Server should listen on port 8000 on all interfaces!
