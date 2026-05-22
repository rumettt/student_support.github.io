from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "students.json"

NAME_RE = re.compile(r"^[A-Za-z]+(?: [A-Za-z]+)*$")
EMAIL_RE = re.compile(r"^(?!\d+@)[a-z0-9._%+-]+@[a-z0-9-]*[a-z][a-z0-9-]*(\.[a-z]{2,})+$", re.I)


def password_problem(password):
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must include at least one capital letter"
    if not re.search(r"[a-z]", password):
        return "Password must include at least one small letter"
    if not re.search(r"\d", password):
        return "Password must include at least one number"
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Password must include at least one symbol"
    return ""


def read_students():
    DATA_DIR.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("{}", encoding="utf-8")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def write_students(students):
    DATA_DIR.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(students, indent=2), encoding="utf-8")


class AdvisorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if self.path == "/api/health":
            self.send_json(200, {"ok": True})
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/signup":
                self.signup()
            elif self.path == "/api/signin":
                self.signin()
            elif self.path == "/api/save":
                self.save_student()
            else:
                self.send_json(404, {"error": "Endpoint not found"})
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def signup(self):
        data = self.read_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        name = data.get("name", "").strip()
        if not email or not password or not name:
            self.send_json(400, {"error": "Name, email, and password are required"})
            return
        if not NAME_RE.fullmatch(name):
            self.send_json(400, {"error": "Name must contain letters only, with spaces allowed between names"})
            return
        if not EMAIL_RE.fullmatch(email):
            self.send_json(400, {"error": "Enter a valid email with @ and a provider domain"})
            return
        problem = password_problem(password)
        if problem:
            self.send_json(400, {"error": problem})
            return
        students = read_students()
        if email in students:
            self.send_json(409, {"error": "An account already exists for this email"})
            return
        student = {
            "name": name,
            "email": email,
            "password": password,
            "target": int(data.get("target") or 122),
            "minGpa": float(data.get("minGpa") or 2.0),
            "registration": "May 28, 2026",
            "transcript": [],
            "plan": [],
            "customCourses": {},
        }
        students[email] = student
        write_students(students)
        self.send_json(201, {"student": public_student(student)})

    def signin(self):
        data = self.read_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        email_problem = not EMAIL_RE.fullmatch(email)
        password_error = password_problem(password)
        if email_problem or password_error:
            self.send_json(400, {"error": "Enter a valid email and strong password"})
            return
        student = read_students().get(email)
        if not student or student.get("password") != password:
            self.send_json(401, {"error": "Email or password is incorrect"})
            return
        self.send_json(200, {"student": public_student(student)})

    def save_student(self):
        data = self.read_json()
        email = data.get("email", "").strip().lower()
        students = read_students()
        if email not in students:
            self.send_json(404, {"error": "Student account not found"})
            return
        students[email]["transcript"] = data.get("transcript", [])
        students[email]["plan"] = data.get("plan", [])
        students[email]["customCourses"] = data.get("customCourses", students[email].get("customCourses", {}))
        students[email]["target"] = int(data.get("target") or students[email].get("target", 122))
        students[email]["minGpa"] = float(data.get("minGpa") or students[email].get("minGpa", 2.0))
        write_students(students)
        self.send_json(200, {"student": public_student(students[email])})


def public_student(student):
    return {key: value for key, value in student.items() if key != "password"}


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8000
    print(f"Student Academic Advisor running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), AdvisorHandler).serve_forever()
