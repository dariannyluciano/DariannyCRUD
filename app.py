from contextlib import contextmanager
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sqlite3


DB_PATH = Path("estudiantes.db")
PORT = 8000


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
        <div>
            <h1>CRUD de Estudiantes</h1>
            <p>Registro basico para gestionar estudiantes.</p>
        </div>
        <a class="button" href="/nuevo">Nuevo estudiante</a>
    </header>
    <main class="container">
        {message_html}
        {content}
    </main>
</body>
</html>"""


def index_page(message="", search=""):
    estudiantes = get_estudiantes(search)
    search_value = escape(search)

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
            rows += f"""
                <tr>
                    <td>{escape(estudiante["nombre"])}</td>
                    <td>{escape(estudiante["matricula"])}</td>
                    <td>{escape(estudiante["carrera"])}</td>
                    <td>{escape(estudiante["correo"])}</td>
                    <td class="actions">
                        <a href="/detalle?id={estudiante["id"]}">Ver</a>
                        <a href="/editar?id={estudiante["id"]}">Editar</a>
                        <form action="/eliminar?id={estudiante["id"]}" method="post">
                            <button type="submit">Eliminar</button>
                        </form>
                    </td>
                </tr>
            """
        rows += "</tbody></table>"

    content = f"""
    <section class="panel">
        <h2>Listado de estudiantes</h2>
        <form class="search-form" action="/" method="get">
            <input type="text" name="buscar" value="{search_value}" placeholder="Buscar estudiante">
            <button type="submit">Buscar</button>
            <a href="/">Limpiar</a>
        </form>
        {rows}
    </section>
    """
    return page("CRUD de Estudiantes", content, message)


def form_page(estudiante=None, message=""):
    title = "Editar estudiante" if estudiante else "Nuevo estudiante"
    action = f'/actualizar?id={estudiante["id"]}' if estudiante else "/crear"

    nombre = estudiante["nombre"] if estudiante else ""
    matricula = estudiante["matricula"] if estudiante else ""
    carrera = estudiante["carrera"] if estudiante else ""
    correo = estudiante["correo"] if estudiante else ""

    content = f"""
    <section class="panel form-panel">
        <h2>{title}</h2>
        <form action="{action}" method="post">
            <label>Nombre
                <input type="text" name="nombre" value="{escape(nombre)}" required>
            </label>
            <label>Matricula
                <input type="text" name="matricula" value="{escape(matricula)}" required>
            </label>
            <label>Carrera
                <input type="text" name="carrera" value="{escape(carrera)}" required>
            </label>
            <label>Correo
                <input type="email" name="correo" value="{escape(correo)}" required>
            </label>
            <div class="form-actions">
                <button class="button" type="submit">Guardar</button>
                <a href="/">Cancelar</a>
            </div>
        </form>
    </section>
    """
    return page(title, content, message)


def detail_page(estudiante):
    content = f"""
    <section class="panel detail">
        <h2>Detalle del estudiante</h2>
        <p><strong>Nombre:</strong> {escape(estudiante["nombre"])}</p>
        <p><strong>Matricula:</strong> {escape(estudiante["matricula"])}</p>
        <p><strong>Carrera:</strong> {escape(estudiante["carrera"])}</p>
        <p><strong>Correo:</strong> {escape(estudiante["correo"])}</p>
        <div class="form-actions">
            <a class="button" href="/editar?id={estudiante["id"]}">Editar</a>
            <a href="/">Volver</a>
        </div>
    </section>
    """
    return page("Detalle del estudiante", content)


def parse_form(body):
    fields = parse_qs(body)
    return {key: values[0] for key, values in fields.items()}


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

    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)

        if parsed_url.path == "/":
            search = params.get("buscar", [""])[0].strip()
            self.send_html(index_page(search=search))
        elif parsed_url.path == "/nuevo":
            self.send_html(form_page())
        elif parsed_url.path == "/detalle":
            estudiante = get_estudiante(int(params.get("id", [0])[0]))
            if estudiante:
                self.send_html(detail_page(estudiante))
            else:
                self.send_html(index_page("Estudiante no encontrado."))
        elif parsed_url.path == "/editar":
            estudiante = get_estudiante(int(params.get("id", [0])[0]))
            if estudiante:
                self.send_html(form_page(estudiante))
            else:
                self.send_html(index_page("Estudiante no encontrado."))
        elif parsed_url.path == "/static/style.css":
            css_path = Path("static/style.css")
            body = css_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
                self.send_html(form_page(None, error))
            else:
                self.send_html(index_page("Estudiante registrado correctamente."))
        elif parsed_url.path == "/actualizar":
            estudiante_id = int(params.get("id", [0])[0])
            error = actualizar_estudiante(estudiante_id, data)
            if error:
                estudiante = get_estudiante(estudiante_id)
                self.send_html(form_page(estudiante, error))
            else:
                self.send_html(index_page("Estudiante actualizado correctamente."))
        elif parsed_url.path == "/eliminar":
            estudiante_id = int(params.get("id", [0])[0])
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
