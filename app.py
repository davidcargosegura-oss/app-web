import os
from wtforms.fields import PasswordField
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView

# --- Configuración Inicial ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
# ¡IMPORTANTE! Cambia esta clave secreta por una cadena aleatoria y muy larga.
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_larga_y_segura_debes_cambiarla' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'

# Importar el modelo de usuario (definido en models.py)
# Se hace aquí para evitar una importación circular
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def __repr__(self):
        return f'<User {self.username}>'

def init_db_data(db):
    # Crear el usuario administrador por defecto: usuario: davidp, contraseña: admin
    with app.app_context():
        if not User.query.filter_by(username='davidp').first():
            admin_user = User(
                username='davidp',
                is_admin=True
            )
            admin_user.set_password('admin') # Contraseña inicial: admin
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario administrador 'davidp' creado exitosamente.")

# --- Vistas Personalizadas de Flask-Admin (Punto 2: Panel de gestión de usuarios) ---

# 1. Clase para proteger las vistas de Flask-Admin
class ProtectedAdminView(ModelView):
    # Campo para ingresar la contraseña, que NO es el mismo que el campo de la DB (password_hash)
    form_extra_fields = {
        'password': PasswordField('Contraseña (Dejar vacío para no cambiar)')
    }
    # Ocultar el campo real de la DB para que no se muestre el hash
    form_excluded_columns = ('password_hash',)

    def is_accessible(self):
        # Solo permite el acceso si el usuario está autenticado y es administrador
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('index'))

    # Este método se llama ANTES de guardar el modelo en la DB
    def on_model_change(self, form, model, is_created):
        # 1. Verificar si el usuario ha introducido un valor en el campo extra 'password'
        if 'password' in form and form.password.data:
            # 2. Si lo hizo, aplicar el hash de seguridad y guardarlo en el campo password_hash
            model.password_hash = generate_password_hash(form.password.data)
            
        # 3. Llamar al método base de Flask-Admin
        super(ProtectedAdminView, self).on_model_change(form, model, is_created)

class MyAdminIndexView(AdminIndexView):
    # Función que verifica si el usuario tiene permiso para acceder a esta página
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    # Función que se ejecuta si el acceso es denegado
    def inaccessible_callback(self, name, **kwargs):
        # Si el usuario NO es admin, forzar la redirección a la página principal.
        # Esto previene que se quede atrapado en el loop de login.
        flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('index'))

# --- Inicialización de Flask-Admin ---
admin = Admin(
    app,
    name='Gestor de Tráfico Admin',
    # Eliminamos 'template_mode' para evitar el error de la versión
    index_view=MyAdminIndexView(name='Dashboard', url='/admin')
)
admin.add_view(ProtectedAdminView(User, db.session, name='Usuarios'))

# --- Rutas de la Aplicación ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ruta de la página principal (requiere login)
@app.route('/')
@login_required
def index():
    # Carga el contenido de tu archivo HTML original
    original_file_name = 'app planing grupajes 12 - ultimo bueno.html'
    try:
        with open(original_file_name, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template('index.html', original_content=content)
    except FileNotFoundError:
        flash(f'Advertencia: El archivo HTML original "{original_file_name}" no se encontró.', 'danger')
        return render_template('index.html', original_content='<h1>Contenido Base</h1><p>Archivo principal de la app no cargado.</p>')

# Ruta de Login (Punto 1: Formulario de login)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.index'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Por favor, comprueba tus datos de login e inténtalo de nuevo.', 'danger')
            return redirect(url_for('login'))

        login_user(user, remember=remember)

        next_page = request.args.get('next')
        
        # FIX: Si el usuario NO es admin, NUNCA debe ser redirigido a una ruta admin
        # incluso si la URL 'next' lo indica (por haber sido rechazado inicialmente).
        if next_page and not user.is_admin and ('/admin' in next_page or '/admin/' in next_page):
             flash('Acceso denegado al panel de administración.', 'danger')
             # Forzar la redirección a la página principal estándar (index)
             return redirect(url_for('index'))

        # Si el usuario es admin y no se solicitó una página específica, 
        # lo mandamos al dashboard admin por defecto.
        if user.is_admin and not next_page:
             return redirect(url_for('admin.index'))
             
        # Redirigir a la página solicitada (next_page, que ahora es segura) o a la principal.
        return redirect(next_page or url_for('index'))

    return render_template('login.html')

# Ruta de Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('login'))

# --- Ejecución de la Aplicación ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db_data(db) # Inicializa el usuario davidp:admin (Punto 3)

    app.run(debug=True)