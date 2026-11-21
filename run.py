#!/usr/bin/env python3
"""Development server: rebuilds the database and reloads on change."""
from dashmachine import create_app
from dashmachine.main.utils import dashmachine_init

app = create_app(DEBUG=True)
dashmachine_init(app)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, host="0.0.0.0", threaded=True)
