# ODDI React Sidebar

This is a standalone React/Vite sidebar sidecar for the existing Flask ODDI app.

1. Run `npm.cmd install`
2. Run `npm.cmd run build`
3. Copy `dist/oddi-sidebar.js` and `dist/oddi-sidebar.css` to `static/oddi-sidebar/`
4. Add before `</body>` in `templates/index.html`:
   `<link rel="stylesheet" href="{{ url_for('static', filename='oddi-sidebar/oddi-sidebar.css') }}">`
   `<script type="module" src="{{ url_for('static', filename='oddi-sidebar/oddi-sidebar.js') }}"></script>`

Do not delete the existing `frontend` folder. This package belongs inside it.
