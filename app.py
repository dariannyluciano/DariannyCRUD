from contextlib import contextmanager
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "estudiantes.db"
STYLE_PATH = BASE_DIR / "static" / "style.css"
PORT = 8000
CARRERAS = [
    "Software",
    "Redes",
    "Multimedia",
    "Mecatronica",
    "Seguridad Informatica",
]


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                matricula TEXT NOT NULL UNIQUE,
                carrera TEXT NOT NULL,
                correo TEXT NOT NULL
            )
            """
        )


def get_estudiantes(search=""):
    with get_connection() as connection:
        if search:
            value = f"%{search}%"
            return connection.execute(
                """
                SELECT * FROM estudiantes
                WHERE nombre LIKE ? OR matricula LIKE ? OR carrera LIKE ?
                ORDER BY id DESC
                """,
                (value, value, value),
            ).fetchall()

        return connection.execute(
            "SELECT * FROM estudiantes ORDER BY id DESC"
        ).fetchall()


def get_estudiante(estudiante_id):
    with get_connection() as connection:
        return connection.execute(
            "SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)
        ).fetchone()


def correo_valido(correo):
    if "@" not in correo:
        return False

    usuario, dominio = correo.split("@", 1)
    return bool(usuario and "." in dominio and dominio.rsplit(".", 1)[-1])


def guardar_estudiante(data):
    nombre = data.get("nombre", "").strip()
    matricula = data.get("matricula", "").strip()
    carrera = data.get("carrera", "").strip()
    correo = data.get("correo", "").strip()

    if not nombre or not matricula or not carrera or not correo:
        return "Todos los campos son obligatorios."

    if not correo_valido(correo):
        return "El correo electronico no es valido."

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO estudiantes (nombre, matricula, carrera, correo)
                VALUES (?, ?, ?, ?)
                """,
                (nombre, matricula, carrera, correo),
            )
        return ""
    except sqlite3.IntegrityError:
        return "Ya existe un estudiante con esa matricula."


def actualizar_estudiante(estudiante_id, data):
    nombre = data.get("nombre", "").strip()
    matricula = data.get("matricula", "").strip()
    carrera = data.get("carrera", "").strip()
    correo = data.get("correo", "").strip()

    if not nombre or not matricula or not carrera or not correo:
        return "Todos los campos son obligatorios."

    if not correo_valido(correo):
        return "El correo electronico no es valido."

    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE estudiantes
                SET nombre = ?, matricula = ?, carrera = ?, correo = ?
                WHERE id = ?
                """,
                (nombre, matricula, carrera, correo, estudiante_id),
            )
        return ""
    except sqlite3.IntegrityError:
        return "Ya existe un estudiante con esa matricula."


def eliminar_estudiante(estudiante_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM estudiantes WHERE id = ?", (estudiante_id,))


def value_from(item, key):
    if not item:
        return ""
    value = item[key] if key in item.keys() else ""
    return "" if value is None else str(value)


def item_has_id(item):
    return bool(item and "id" in item.keys() and str(item["id"]).strip())


def page(title, content, message=""):
    message_html = ""
    if message:
        message_html = f'<section class="message">{escape(message)}</section>'

    return f"""<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(title)}</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header class="header">
        <div class="header-inner">
            <div>
                <h1>Registro</h1>
            </div>
            <a class="button header-button" href="/?form=nuevo">Nuevo estudiante</a>
        </div>
    </header>
    <main class="container">
        {message_html}
        {content}
    </main>
</body>
</html>"""


def form_section(estudiante=None, message=""):
    editing = item_has_id(estudiante)
    title = "Editar estudiante" if editing else "Nuevo estudiante"
    action = f'/actualizar?id={estudiante["id"]}' if editing else "/crear"

    nombre = value_from(estudiante, "nombre")
    matricula = value_from(estudiante, "matricula")
    carrera = value_from(estudiante, "carrera")
    correo = value_from(estudiante, "correo")
    opciones_carrera = ""

    for opcion in CARRERAS:
        selected = " selected" if opcion == carrera else ""
        opciones_carrera += f'<option value="{escape(opcion)}"{selected}>{escape(opcion)}</option>'

    message_html = ""
    if message:
        message_html = f'<p class="form-message">{escape(message)}</p>'

    return f"""
    <section class="panel form-panel" id="formulario">
        <div class="panel-title">
            <span class="icon-box">+</span>
            <h2>{title}</h2>
        </div>
        {message_html}
        <form action="{action}" method="post">
            <label>Nombre
                <input type="text" name="nombre" value="{escape(nombre)}" required>
            </label>
            <label>Matricula
                <input type="text" name="matricula" value="{escape(matricula)}" required>
            </label>
            <label>Carrera
                <select name="carrera" required>
                    <option value="">Seleccione una carrera</option>
                    {opciones_carrera}
                </select>
            </label>
            <label>Correo
                <input type="email" name="correo" value="{escape(correo)}" required>
            </label>
            <div class="form-actions">
                <button class="button" type="submit">Guardar</button>
                <a class="link-button" href="/">Cancelar</a>
            </div>
        </form>
    </section>
    """


def index_page(message="", search="", form_item=None, form_message=""):
    estudiantes = get_estudiantes(search)
    search_value = escape(search)
    form_html = form_section(form_item, form_message) if form_item is not None else ""
    grid_class = "content-grid with-form" if form_html else "content-grid"

    if not estudiantes:
        rows = '<p class="empty">No hay estudiantes registrados.</p>'
    else:
        rows = """
        <table>
            <thead>
                <tr>
                    <th>Nombre</th>
                    <th>Matricula</th>
                    <th>Carrera</th>
                    <th>Correo</th>
                    <th>Acciones</th>
                </tr>
            </thead>
            <tbody>
        """
        for estudiante in estudiantes:
            estudiante_id = estudiante["id"]
            rows += f"""
                <tr>
                    <td><strong>{escape(estudiante["nombre"])}</strong></td>
                    <td>{escape(estudiante["matricula"])}</td>
                    <td>{escape(estudiante["carrera"])}</td>
                    <td>{escape(estudiante["correo"])}</td>
                    <td class="actions">
                        <a class="small-button" href="/detalle?id={estudiante_id}">Ver</a>
                        <a class="small-button" href="/?editar={estudiante_id}">Editar</a>
                        <form action="/eliminar?id={estudiante_id}" method="post">
                            <button class="small-button danger" type="submit">Eliminar</button>
                        </form>
                    </td>
                </tr>
            """
        rows += "</tbody></table>"

    content = f"""
    <div class="{grid_class}">
        <section class="panel list-panel">
            <div class="panel-title">
                <h2>Listado de estudiantes</h2>
            </div>
            <p class="total">Total registrados: {len(estudiantes)}</p>
            <form class="search-form" action="/" method="get">
                <input type="text" name="buscar" value="{search_value}" placeholder="Buscar estudiante">
                <button type="submit">Buscar</button>
                <a class="link-button" href="/">Limpiar</a>
            </form>
            <div class="table-area">
                {rows}
            </div>
        </section>
        {form_html}
    </div>
    """
    return page("Registro", content, message)


def form_page(estudiante=None, message=""):
    return page("Formulario de estudiante", form_section(estudiante, message))


def detail_page(estudiante):
    content = f"""
    <section class="panel detail">
        <div class="panel-title">
            <span class="icon-box">i</span>
            <h2>Detalle del estudiante</h2>
        </div>
        <p><strong>Nombre:</strong> {escape(estudiante["nombre"])}</p>
        <p><strong>Matricula:</strong> {escape(estudiante["matricula"])}</p>
        <p><strong>Carrera:</strong> {escape(estudiante["carrera"])}</p>
        <p><strong>Correo:</strong> {escape(estudiante["correo"])}</p>
        <div class="form-actions">
            <a class="button" href="/?editar={estudiante["id"]}">Editar</a>
            <a class="link-button" href="/">Volver</a>
        </div>
    </section>
    """
    return page("Detalle del estudiante", content)


def parse_form(body):
    fields = parse_qs(body)
    return {key: values[0] for key, values in fields.items()}


def obtener_id(params):
    try:
        return int(params.get("id", [0])[0])
    except ValueError:
        return 0


class EstudiantesHandler(BaseHTTPRequestHandler):
    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def send_css(self):
        body = STYLE_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)

        if parsed_url.path == "/":
            search = params.get("buscar", [""])[0].strip()
            message = ""
            form_item = None

            if params.get("form", [""])[0] == "nuevo":
                form_item = {}
            elif "editar" in params:
                form_item = get_estudiante(obtener_id({"id": params["editar"]}))
                if not form_item:
                    message = "Estudiante no encontrado."

            self.send_html(index_page(message=message, search=search, form_item=form_item))
        elif parsed_url.path == "/nuevo":
            self.redirect("/?form=nuevo")
        elif parsed_url.path == "/detalle":
            estudiante = get_estudiante(obtener_id(params))
            if estudiante:
                self.send_html(detail_page(estudiante))
            else:
                self.send_html(index_page("Estudiante no encontrado."))
        elif parsed_url.path == "/editar":
            estudiante_id = obtener_id(params)
            self.redirect(f"/?editar={estudiante_id}")
        elif parsed_url.path == "/static/style.css":
            self.send_css()
        else:
            self.send_html(page("No encontrado", "<h2>Pagina no encontrada</h2>"), 404)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        content_length = int(self.headers.get("Content-Length", 0))
        data = parse_form(self.rfile.read(content_length).decode("utf-8"))

        if parsed_url.path == "/crear":
            error = guardar_estudiante(data)
            if error:
                self.send_html(index_page(form_item=data, form_message=error))
            else:
                self.send_html(index_page("Estudiante registrado correctamente."))
        elif parsed_url.path == "/actualizar":
            estudiante_id = obtener_id(params)
            if not get_estudiante(estudiante_id):
                self.send_html(index_page("Estudiante no encontrado."))
                return

            error = actualizar_estudiante(estudiante_id, data)
            if error:
                form_item = dict(data)
                form_item["id"] = str(estudiante_id)
                self.send_html(index_page(form_item=form_item, form_message=error))
            else:
                self.send_html(index_page("Estudiante actualizado correctamente."))
        elif parsed_url.path == "/eliminar":
            estudiante_id = obtener_id(params)
            if not get_estudiante(estudiante_id):
                self.send_html(index_page("Estudiante no encontrado."))
                return

            eliminar_estudiante(estudiante_id)
            self.send_html(index_page("Estudiante eliminado correctamente."))
        else:
            self.redirect("/")


def run():
    init_db()
    server = HTTPServer(("localhost", PORT), EstudiantesHandler)
    print(f"Servidor iniciado en http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()






