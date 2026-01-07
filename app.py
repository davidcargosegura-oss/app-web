
import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms.fields import PasswordField
import json

# --- 1. CONFIGURACIÓN INICIAL DE LA APLICACIÓN ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# Configuración de Seguridad y Base de Datos
# Configuración de Seguridad y Base de Datos
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') or 'una_clave_secreta_local_para_pruebas_DEBES_CAMBIARLA'

# Database Configuration: Prefer DATABASE_URL (for Render), fallback to SQLite (for local)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' 

# --- 2. MODELOS DE BASE DE DATOS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        # Usamos pbkdf2:sha256 para asegurar que el hash quepa en VARCHAR(128)
        # scrypt (default en nuevas versiones) genera hashes más largos.
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Truck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(100), default='')
    location_last_updated = db.Column(db.String(20), default='2000-01-01') 
    creation_date = db.Column(db.String(20), nullable=False)
    deletion_date = db.Column(db.String(20), nullable=True)
    is_location_manual = db.Column(db.Boolean, default=False)
    is_zone_manual = db.Column(db.Boolean, default=False)
    zones_str = db.Column(db.String(200), default='')
    manual_location = db.Column(db.String(100), default='') 
    zones_last_updated = db.Column(db.String(20), default='2000-01-01')
    # NEW: Additional truck info (optional, not shown on main card)
    trailer = db.Column(db.String(50), default='')
    driver_name = db.Column(db.String(100), default='')
    driver_phone = db.Column(db.String(20), default='')
    driver_dni = db.Column(db.String(20), default='')
    driver_alias = db.Column(db.String(50), default='')
    manual_zones_str = db.Column(db.String(200), default='')  # NEW: Manual zones selected by user
    history_str = db.Column(db.Text, default='[]') # NEW: JSON string for history [{date, trailer, driver_name...}]

    def to_dict(self):
        return {
            'id': self.id,
            'plate': self.plate,
            'location': self.location,
            'locationLastUpdatedDate': self.location_last_updated,
            'creationDate': self.creation_date,
            'deletionDate': self.deletion_date,
            'isLocationManual': self.is_location_manual,
            'isZoneManual': self.is_zone_manual,
            'zones': self.zones_str.split(',') if self.zones_str else [],
            'zonesLastUpdatedDate': self.zones_last_updated,
            'manualLocation': self.manual_location,
            'manualZones': self.manual_zones_str.split(',') if self.manual_zones_str else [],
            'trailer': self.trailer,
            'driverName': self.driver_name,
            'driverPhone': self.driver_phone,
            'driverDni': self.driver_dni,
            'driverAlias': self.driver_alias,
            'history': json.loads(self.history_str) if self.history_str else []
        }

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20), default='')
    phone = db.Column(db.String(20), default='')
    alias = db.Column(db.String(50), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'dni': self.dni,
            'phone': self.phone,
            'alias': self.alias
        }

class Trailer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    type = db.Column(db.String(50), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'plate': self.plate,
            'type': self.type
        }
class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False) # 'departure', 'return'
    client = db.Column(db.String(100), nullable=False)
    driver = db.Column(db.String(100), default='')
    origin = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    destination_zone = db.Column(db.String(50), nullable=True) # NEW: Destination Zone
    load_date = db.Column(db.String(20), nullable=False)
    unload_date = db.Column(db.String(20), nullable=False)
    
    assigned_truck_plate = db.Column(db.String(20), db.ForeignKey('truck.plate'), nullable=True)
    assigned_slot = db.Column(db.Integer, nullable=True)
    
    is_urgent = db.Column(db.Boolean, default=False)
    is_groupage = db.Column(db.Boolean, default=False)
    zone = db.Column(db.String(50), nullable=True)
    
    pg = db.Column(db.Integer, default=0)
    ep = db.Column(db.Integer, default=0)
    pp = db.Column(db.Integer, default=0)
    
    notify_time = db.Column(db.String(20), default="")
    is_notified = db.Column(db.Boolean, default=False)

    assigned_truck = db.relationship('Truck', backref=db.backref('trips', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'client': self.client,
            'driver': self.driver,
            'origin': self.origin,
            'destination': self.destination,
            'destinationZone': self.destination_zone,
            'loadDate': self.load_date,
            'unloadDate': self.unload_date,
            'assignedTruck': self.assigned_truck_plate,
            'assignedSlot': self.assigned_slot,
            'isUrgent': self.is_urgent,
            'isGroupage': self.is_groupage,
            'zone': self.zone,
            'pg': self.pg,
            'ep': self.ep,
            'pp': self.pp,
            'notifyTime': self.notify_time,
            'isNotified': self.is_notified
        }
# ...








class DailyNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, default='')
    __table_args__ = (db.UniqueConstraint('date', 'type', name='unique_date_type'),)

class TruckFds(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    truck_plate = db.Column(db.String(20), db.ForeignKey('truck.plate'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    is_out_of_service = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint('truck_plate', 'date', name='unique_plate_date'),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 3. VISTAS ADMIN ---
class ProtectedAdminView(ModelView):
    form_extra_fields = {'password': PasswordField('Contraseña')}
    form_excluded_columns = ('password_hash',)

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('index'))

    def on_model_change(self, form, model, is_created):
        if 'password' in form and form.password.data:
            model.password_hash = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        super(ProtectedAdminView, self).on_model_change(form, model, is_created)

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index'))

admin = Admin(app, name='Gestor Tráfico', index_view=MyAdminIndexView(name='Dashboard', url='/admin'))

# Add link back to traffic manager
from flask_admin.menu import MenuLink
admin.add_link(MenuLink(name='← Gestor de Tráfico', url='/'))

admin.add_view(ProtectedAdminView(User, db.session, name='Usuarios'))
admin.add_view(ProtectedAdminView(Truck, db.session, name='Camiones'))
admin.add_view(ProtectedAdminView(Trip, db.session, name='Viajes'))
admin.add_view(ProtectedAdminView(DailyNote, db.session, name='Notas'))
admin.add_view(ProtectedAdminView(Driver, db.session, name='Conductores')) # Add Driver to Admin
admin.add_view(ProtectedAdminView(Trailer, db.session, name='Remolques')) # Add Trailer to Admin

# --- 4. INIT & RUTAS BASIVAS ---
# --- 4. INIT & RUTAS BASIVAS ---
# --- 4. INIT & RUTAS BASIVAS ---
# Flag global para controlar la inicialización por worker
_db_initialized = False

@app.before_request
def init_db_on_first_request():
    global _db_initialized
    if not _db_initialized:
        try:
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"Tablas existentes antes de check: {tables}")
            
            db.create_all() # This will create Driver and Trailer tables if they don't exist

            # MIGRATION: Check for new columns
            try:
                with db.engine.connect() as conn:
                    # Check Truck columns
                    truck_columns = [c['name'] for c in inspector.get_columns('truck')]
                    if 'manual_location' not in truck_columns:
                        print("Migrando base de datos: Añadiendo manual_location a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN manual_location VARCHAR(100) DEFAULT ''"))
                    if 'is_zone_manual' not in truck_columns:
                        print("Migrando base de datos: Añadiendo is_zone_manual a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN is_zone_manual BOOLEAN DEFAULT 0"))
                    if 'zones_last_updated' not in truck_columns:
                        print("Migrando base de datos: Añadiendo zones_last_updated a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN zones_last_updated VARCHAR(20) DEFAULT '2000-01-01'"))
                    if 'manual_zones_str' not in truck_columns:
                        print("Migrando base de datos: Añadiendo manual_zones_str a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN manual_zones_str VARCHAR(200) DEFAULT ''"))
                    if 'trailer' not in truck_columns:
                        print("Migrando base de datos: Añadiendo trailer a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN trailer VARCHAR(50) DEFAULT ''"))
                    if 'driver_name' not in truck_columns:
                        print("Migrando base de datos: Añadiendo driver_name a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN driver_name VARCHAR(100) DEFAULT ''"))
                    if 'driver_phone' not in truck_columns:
                        print("Migrando base de datos: Añadiendo driver_phone a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN driver_phone VARCHAR(20) DEFAULT ''"))
                    if 'driver_dni' not in truck_columns:
                        print("Migrando base de datos: Añadiendo driver_dni a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN driver_dni VARCHAR(20) DEFAULT ''"))
                    if 'driver_alias' not in truck_columns:
                        print("Migrando base de datos: Añadiendo driver_alias a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN driver_alias VARCHAR(50) DEFAULT ''"))
                    if 'history_str' not in truck_columns:
                        print("Migrando base de datos: Añadiendo history_str a truck...")
                        conn.execute(text("ALTER TABLE truck ADD COLUMN history_str TEXT DEFAULT '[]'"))
                    
                    # Check Trip columns
                    trip_columns = [c['name'] for c in inspector.get_columns('trip')]
                    if 'destination_zone' not in trip_columns:
                        print("Migrando base de datos: Añadiendo destination_zone a trip...")
                        conn.execute(text("ALTER TABLE trip ADD COLUMN destination_zone VARCHAR(50)"))
                        
                    conn.commit()
            except Exception as e:
                print(f"Error checking/migrating schema: {e}")
            
            if not User.query.filter_by(username='davidp').first():
                u = User(username='davidp', is_admin=True)
                u.set_password('admin')
                db.session.add(u)
                db.session.commit()
                print("Admin 'davidp' creado.")
            
            _db_initialized = True
            print("Base de datos inicializada correctamente.")
        except Exception as e:
            print(f"Error inicializando base de datos: {e}")

# (Funcion anterior create_db_and_admin eliminada/reemplazada por este hook)

# create_db_and_admin() removed in favor of before_request hook

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and u.check_password(request.form.get('password')):
            login_user(u)
            flash('Login exitoso', 'success')
            next_p = request.args.get('next')
            if next_p and not current_user.is_admin and '/admin' in next_p: return redirect(url_for('index'))
            if current_user.is_admin and not next_p: return redirect(url_for('admin.index'))
            return redirect(next_p or url_for('index'))
        else: flash('Datos incorrectos', 'danger')
    return render_template('login.html', title='Login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', title='Gestor de Tráfico')

# --- 5. API ENDPOINTS ---
@app.route('/api/initial-data')
@login_required
def get_initial_data():
    try:
        # print("DEBUG: Invocando get_initial_data")
        # Ensure schema is up to date if _db_initialized logic failed?
        # Manually triggering helper check? No, rely on before_request.
        
        # Helper to safely serialize
        def safe_dict(obj, model_name):
            try:
                return obj.to_dict()
            except Exception as e:
                print(f"ERROR serializing {model_name} ID {getattr(obj, 'id', 'unknown')}: {e}")
                raise e

        trucks = [safe_dict(t, 'Truck') for t in Truck.query.all()]
        # print(f"DEBUG: {len(trucks)} camiones cargados.")
        
        trips = [safe_dict(t, 'Trip') for t in Trip.query.all()]
        # print(f"DEBUG: {len(trips)} viajes cargados.")

        drivers = [safe_dict(d, 'Driver') for d in Driver.query.all()]
        trailers = [safe_dict(t, 'Trailer') for t in Trailer.query.all()]
        
        fds_records = [
            {'plate': r.truck_plate, 'date': r.date, 'is_out_of_service': r.is_out_of_service} 
            for r in TruckFds.query.all()
        ]
        return jsonify({'trucks': trucks, 'trips': trips, 'fds_data': fds_records, 'drivers': drivers, 'trailers': trailers})
    except Exception as e:
        print(f"CRITICAL ERROR in get_initial_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/trucks', methods=['POST'])
@login_required
def save_truck():
    d = request.json
    t = Truck.query.filter_by(plate=d.get('plate')).first()
    if not t:
        t = Truck(plate=d.get('plate'))
        db.session.add(t)
    t.location = d.get('location', '')
    t.location_last_updated = d.get('locationLastUpdatedDate', '2000-01-01')
    t.creation_date = d.get('creationDate', '2000-01-01')
    t.deletion_date = d.get('deletionDate')
    t.is_location_manual = d.get('isLocationManual', False)
    t.is_zone_manual = d.get('isZoneManual', False)
    t.zones_str = ','.join(d.get('zones', []))
    t.zones_last_updated = d.get('zonesLastUpdatedDate', '2000-01-01')
    t.manual_location = d.get('manualLocation', '')
    t.manual_zones_str = ','.join(d.get('manualZones', []))
    # NEW: Additional truck info
    t.trailer = d.get('trailer', '')
    t.driver_name = d.get('driverName', '')
    t.driver_phone = d.get('driverPhone', '')
    t.driver_dni = d.get('driverDni', '')
    t.driver_alias = d.get('driverAlias', '')
    
    # NEW: History Logic
    # We expect 'effectiveDate' in the request if this is a temporal update.
    # If not provided, we assume it's an update to the "current" state (which we still mirror in main cols).
    effective_date = d.get('effectiveDate')
    if effective_date:
        import json
        try:
            history = json.loads(t.history_str or '[]')
        except:
            history = []
            
        # Create new history entry
        new_entry = {
            'date': effective_date,
            'trailer': t.trailer,
            'driverName': t.driver_name,
            'driverPhone': t.driver_phone,
            'driverDni': t.driver_dni,
            'driverAlias': t.driver_alias,
            'manualLocation': t.manual_location,
            'manualZones': t.manual_zones_str.split(',') if t.manual_zones_str else []
        }
        
        # Remove existing entry for this date if any
        history = [h for h in history if h.get('date') != effective_date]
        history.append(new_entry)
        
        # Sort by date
        history.sort(key=lambda x: x.get('date'))
        
        t.history_str = json.dumps(history)

    db.session.commit()
    return jsonify(t.to_dict())

@app.route('/api/trucks/<string:plate>', methods=['DELETE'])
@login_required
def delete_truck(plate):
    # This endpoint might remain unused if we only use soft-delete via save_truck, 
    # but good to have for cleanup if needed.
    t = Truck.query.filter_by(plate=plate).first()
    if t:
        db.session.delete(t)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/trips', methods=['POST'])
@login_required
def save_trip():
    d = request.json
    tid = d.get('id')
    t = Trip.query.get(tid) if tid else None
    if not t:
        t = Trip()
        db.session.add(t)
    
    # print(f"DEBUG: Guardando viaje. ID: {tid}, Datos: {d}")
    
    t.type = d.get('type')
    t.client = d.get('client')
    t.driver = d.get('driver')
    t.origin = d.get('origin')
    t.destination = d.get('destination')
    t.destination_zone = d.get('destinationZone') # NEW
    t.load_date = d.get('loadDate')
    t.unload_date = d.get('unloadDate')
    
    # Handle nullable foreign key for truck
    t.assigned_truck_plate = d.get('assignedTruck') or None 
    t.assigned_slot = d.get('assignedSlot')
    
    t.is_urgent = d.get('isUrgent', False)
    t.is_groupage = d.get('isGroupage', False)
    t.zone = d.get('zone')
    t.pg = d.get('pg', 0)
    t.ep = d.get('ep', 0)
    t.pp = d.get('pp', 0)
    
    t.notify_time = d.get('notifyTime', '')
    t.is_notified = d.get('isNotified', False)
    
    db.session.commit()
    # print(f"DEBUG: Viaje guardado correctamente. ID: {t.id}")
    return jsonify(t.to_dict())

@app.route('/api/trips/<int:tid>', methods=['DELETE'])
@login_required
def delete_trip(tid):
    t = Trip.query.get(tid)
    if t:
        db.session.delete(t)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/notes', methods=['GET', 'POST'])
@login_required
def notes():
    if request.method == 'GET':
        n = DailyNote.query.filter_by(date=request.args.get('date'), type=request.args.get('type')).first()
        return jsonify({'content': n.content if n else ''})
    d = request.json
    n = DailyNote.query.filter_by(date=d.get('date'), type=d.get('type')).first()
    if not n:
        n = DailyNote(date=d.get('date'), type=d.get('type'))
        db.session.add(n)
    n.content = d.get('content', '')
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/fds', methods=['POST'])
@app.route('/api/toggle-fds', methods=['POST'])  # Alias for frontend compatibility
@login_required
def fds():
    d = request.json
    r = TruckFds.query.filter_by(truck_plate=d.get('plate'), date=d.get('date')).first()
    # Upsert logic: always save the state (True OR False), do not delete.
    if not r:
        db.session.add(TruckFds(truck_plate=d.get('plate'), date=d.get('date'), is_out_of_service=d.get('is_out_of_service')))
    else:
        r.is_out_of_service = d.get('is_out_of_service')
        
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/delete-truck', methods=['POST'])
@login_required
def delete_truck_via_post():
    """Alternative endpoint for frontend that uses POST with JSON body"""
    d = request.json
    plate = d.get('plate')
    if not plate:
        return jsonify({'error': 'Plate is required'}), 400
    t = Truck.query.filter_by(plate=plate).first()
    if t:
        db.session.delete(t)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/update_db_schema')
def update_db_schema():
    """Route to manually add missing columns - works for both PostgreSQL and SQLite"""
    results = []
    try:
        with app.app_context():
            is_postgres = 'postgresql' in str(db.engine.url)
            
            # Define all columns that might need to be added
            truck_columns = [
                ("manual_location", "VARCHAR(100)", "''"),
                ("is_zone_manual", "BOOLEAN", "FALSE"),
                ("zones_last_updated", "VARCHAR(20)", "'2000-01-01'"),
                ("manual_zones_str", "VARCHAR(200)", "''"),
                ("trailer", "VARCHAR(50)", "''"),
                ("driver_name", "VARCHAR(100)", "''"),
                ("driver_phone", "VARCHAR(20)", "''"),
                ("driver_dni", "VARCHAR(20)", "''"),
                ("driver_alias", "VARCHAR(50)", "''"),
                ("history_str", "TEXT", "'[]'"),
            ]
            
            trip_columns = [
                ("destination_zone", "VARCHAR(50)", None),
            ]
            
            if is_postgres:
                # PostgreSQL supports IF NOT EXISTS
                for col_name, col_type, default in truck_columns:
                    sql = f"ALTER TABLE truck ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    if default:
                        sql += f" DEFAULT {default}"
                    db.session.execute(text(sql + ";"))
                    results.append(f"truck.{col_name}: OK (PostgreSQL)")
                
                for col_name, col_type, default in trip_columns:
                    sql = f"ALTER TABLE trip ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    if default:
                        sql += f" DEFAULT {default}"
                    db.session.execute(text(sql + ";"))
                    results.append(f"trip.{col_name}: OK (PostgreSQL)")
            else:
                # SQLite: Need to check if column exists first
                inspector = db.inspect(db.engine)
                existing_truck_cols = [c['name'] for c in inspector.get_columns('truck')]
                existing_trip_cols = [c['name'] for c in inspector.get_columns('trip')]
                
                for col_name, col_type, default in truck_columns:
                    if col_name not in existing_truck_cols:
                        sql = f"ALTER TABLE truck ADD COLUMN {col_name} {col_type}"
                        if default:
                            sql += f" DEFAULT {default}"
                        db.session.execute(text(sql))
                        results.append(f"truck.{col_name}: ADDED (SQLite)")
                    else:
                        results.append(f"truck.{col_name}: EXISTS (SQLite)")
                
                for col_name, col_type, default in trip_columns:
                    if col_name not in existing_trip_cols:
                        sql = f"ALTER TABLE trip ADD COLUMN {col_name} {col_type}"
                        if default:
                            sql += f" DEFAULT {default}"
                        db.session.execute(text(sql))
                        results.append(f"trip.{col_name}: ADDED (SQLite)")
                    else:
                        results.append(f"trip.{col_name}: EXISTS (SQLite)")
            
            db.session.commit()
            return f"Schema updated successfully!<br><br>Results:<br>" + "<br>".join(results)
    except Exception as e:
        import traceback
        return f"Error updating schema: {e}<br><pre>{traceback.format_exc()}</pre>"

# --- DRIVER & TRAILER CRUD ---
@app.route('/api/drivers', methods=['POST'])
@login_required
def save_driver():
    d = request.json
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    driver = Driver(
        name=name,
        dni=d.get('dni', ''),
        phone=d.get('phone', ''),
        alias=d.get('alias', '')
    )
    db.session.add(driver)
    db.session.commit()
    return jsonify(driver.to_dict())

@app.route('/api/drivers/<int:driver_id>', methods=['DELETE'])
@login_required
def delete_driver(driver_id):
    driver = Driver.query.get(driver_id)
    if driver:
        db.session.delete(driver)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/trailers', methods=['POST'])
@login_required
def save_trailer():
    d = request.json
    plate = d.get('plate', '').strip().upper()
    if not plate:
        return jsonify({'error': 'Plate is required'}), 400
    
    # Check for duplicates
    existing = Trailer.query.filter_by(plate=plate).first()
    if existing:
        return jsonify({'error': 'Trailer with this plate already exists'}), 400
        
    trailer = Trailer(
        plate=plate,
        type=d.get('type', '')
    )
    db.session.add(trailer)
    db.session.commit()
    return jsonify(trailer.to_dict())

@app.route('/api/trailers/<int:trailer_id>', methods=['DELETE'])
@login_required
def delete_trailer(trailer_id):
    trailer = Trailer.query.get(trailer_id)
    if trailer:
        db.session.delete(trailer)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/unassign-day', methods=['POST'])
@login_required
def unassign_day():
    date_filter = request.json.get('date')
    if not date_filter:
        return jsonify({'error': 'Date is required'}), 400
        
    # Find all trips for this date that are assigned
    trips_to_update = Trip.query.filter_by(load_date=date_filter).filter(Trip.assigned_truck_plate != None).all()
    
    for t in trips_to_update:
        t.assigned_truck_plate = None
        t.assigned_slot = None
        t.notify_time = ""
        t.is_notified = False
        
    db.session.commit()
    return jsonify({'success': True, 'count': len(trips_to_update)})

if __name__ == '__main__':
    app.run(debug=True)
