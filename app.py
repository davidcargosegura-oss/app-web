
import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.fields import PasswordField

# --- 1. CONFIGURACIÓN INICIAL DE LA APLICACIÓN ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# Configuración de Seguridad y Base de Datos
# LECTURA SEGURA DE LA CLAVE SECRETA (Para Render/Producción)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or 'una_clave_secreta_local_para_pruebas_DEBES_CAMBIARLA'
# Base de datos SQLite (se usará 'database.db' en el directorio raíz)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirige a 'login' si se requiere autenticación

# --- 2. MODELO DE USUARIO (Database Schema) ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128)) # Almacena el hash seguro de la contraseña
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        """Hashea la contraseña para guardarla de forma segura."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica una contraseña contra el hash almacenado."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    """Callback usado por Flask-Login para cargar un usuario."""
    return User.query.get(int(user_id))

# --- 3. VISTAS DE ADMINISTRACIÓN PERSONALIZADAS ---

# Clase para proteger las vistas de Flask-Admin y gestionar el hashing de contraseñas.
class ProtectedAdminView(ModelView):
    # Campo extra en el formulario para introducir la contraseña (no es el campo de la DB)
    form_extra_fields = {
        'password': PasswordField('Contraseña (Dejar vacío para no cambiar)')
    }
    # Oculta el campo real de la DB (password_hash) para que no se muestre el hash
    form_excluded_columns = ('password_hash',)

    def is_accessible(self):
        """Permite el acceso solo si el usuario está autenticado Y es administrador."""
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        """Redirige si el acceso es denegado."""
        flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('index'))

    def on_model_change(self, form, model, is_created):
        """Se ejecuta ANTES de guardar el modelo en la DB."""
        # Si se introdujo un valor en el campo 'password', lo hasheamos y guardamos.
        if 'password' in form and form.password.data:
            model.password_hash = generate_password_hash(form.password.data)
            
        super(ProtectedAdminView, self).on_model_change(form, model, is_created)

# Clase para el índice del panel de administración (Dashboard principal)
class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('index'))

# --- 4. INICIALIZACIÓN DEL PANEL ADMIN ---

admin = Admin(
    app,
    name='Gestor de Tráfico Admin',
    index_view=MyAdminIndexView(name='Dashboard', url='/admin')
)

# Añadir el modelo User al panel de administración con la vista protegida
admin.add_view(ProtectedAdminView(User, db.session, name='Usuarios'))


# --- 5. LÓGICA DE INICIO DE SESIÓN Y USUARIO INICIAL ---

@app.cli.before_app_serving
def create_db_and_admin():
    """Crea la base de datos y un usuario administrador inicial si no existen."""
    try:
        db.create_all()
        # Verificar si ya existe un usuario administrador
        if not User.query.filter_by(username='davidp').first():
            admin_user = User(username='davidp', is_admin=True)
            # La contraseña 'admin' se hashea antes de guardarse
            admin_user.set_password('admin') 
            db.session.add(admin_user)
            db.session.commit()
            print("Base de datos creada y usuario 'davidp' (admin/admin) inicializado.")
    except Exception as e:
        # Esto puede fallar si la DB ya existe, no es crítico a menos que el error sea grave
        print(f"Error al inicializar la DB/Admin: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Si ya está logueado, redirige a la página principal
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('¡Inicio de sesión exitoso!', 'success')
            
            next_page = request.args.get('next')
            
            # FIX: Seguridad al redirigir después del login.
            # 1. Si el usuario NO es admin, NUNCA redirigir a una ruta admin, incluso si 'next' lo indica.
            if next_page and not current_user.is_admin and ('/admin' in next_page):
                 flash('Acceso denegado al panel de administración.', 'danger')
                 return redirect(url_for('index'))

            # 2. Si el usuario es admin y no solicitó una página específica, ir al dashboard admin.
            if current_user.is_admin and not next_page:
                 return redirect(url_for('admin.index'))
                 
            # 3. Redirigir a la página solicitada o a la principal.
            return redirect(next_page or url_for('index'))

        else:
            flash('Por favor, comprueba tus datos de acceso.', 'danger')

    return render_template('login.html', title='Login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

# --- 6. RUTAS DE LA APLICACIÓN ---

@app.route('/')
@login_required # Solo usuarios autenticados pueden acceder
def index():
    # La página principal carga tu HTML original
    return render_template('index.html', title='Gestor de Tráfico')


if __name__ == '__main__':
    # Nota: En Render, Gunicorn ejecutará la aplicación, no este bloque.
    # Esto es solo para pruebas locales.
    app.run(debug=True)
