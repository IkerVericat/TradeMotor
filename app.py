import os
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pymysql
from pymongo import MongoClient
from functools import wraps
from bson.objectid import ObjectId # Para manejar ObjectId de MongoDB
from datetime import datetime


# === Configuración de Flask ===
app = Flask(__name__)
app.secret_key = 'clave-secreta'

# === Configuración de la carpeta de subida de imágenes ===
UPLOAD_FOLDER = "static/images"
app.config["UPLOAD_FOLDER"] = "static/images"


# === Conexiones a bases de datos ===

    # Mariadb

def get_mariadb_connection():
    return pymysql.connect(
        host='192.168.1.12', # IP del servidor
        port=2206,
        user='root',
        password='iker',
        database='TradeMotor'
    )



    # MongoDB

mongo_client = MongoClient('mongodb://admin:adminpassword@192.168.1.12:27017/')    # IP del servidor
mongo_db = mongo_client['TradeMotor']
comentarios_col = mongo_db['comentarios']
favoritos_col = mongo_db['favoritos']
ofertas_col = mongo_db['ofertas']
historial_precios_col = mongo_db['historial_precios']


# === Clase modelo: Coche ===

class Coche:
    def __init__(self, marca, modelo, precio, anyo, tipo, autonomia=None, en_oferta=False, id=None, 
                 tiempo_carga=None, capacidad_bateria=None, tipo_hibrido=None, consumo_mixto=None, imagen_url=None):
        self.id = id
        self.marca = marca
        self.modelo = modelo
        self.precio = round(float(precio), 2)
        self.anyo = anyo
        self.tipo = tipo
        self.autonomia = autonomia
        self.en_oferta = en_oferta
        self.tiempo_carga = tiempo_carga
        self.capacidad_bateria = capacidad_bateria
        self.tipo_hibrido = tipo_hibrido
        self.consumo_mixto = consumo_mixto
        self.imagen_url = imagen_url

    ## Método de clase para crear un coche a partir de un formulario
    @classmethod
    def from_form(cls, form):
        marca = form['marca']
        modelo = form['modelo']
        precio = float(form['precio'])
        anyo = int(form['anyo'])
        tipo = form.get('tipo')

        autonomia = float(form.get('autonomia')) if form.get('autonomia') else None
        en_oferta = 'oferta' in form

        tiempo_carga = float(form.get('tiempo_carga')) if tipo == "electrico" else None
        capacidad_bateria = float(form.get('capacidad_bateria')) if tipo == "electrico" else None
        tipo_hibrido = form.get('tipo_hibrido') if tipo == "hibrido" else None
        consumo_mixto = float(form.get('consumo_mixto')) if tipo == "hibrido" else None

        imagen_url = form.get('imagen_url', "images/default.jpg")


        return cls(marca, modelo, precio, anyo, tipo, autonomia, en_oferta, 
                tiempo_carga=tiempo_carga, capacidad_bateria=capacidad_bateria, 
                tipo_hibrido=tipo_hibrido, consumo_mixto=consumo_mixto, imagen_url=imagen_url)

    
    # Método para guardar el coche en la base de datos
    def save(self):
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            sql = (
                "INSERT INTO coches (marca, modelo, precio, anyo, tipo, autonomia, en_oferta, "
                "tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto, imagen_url) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            )
            params = (self.marca, self.modelo, self.precio, self.anyo, self.tipo, self.autonomia, 
                    int(self.en_oferta), self.tiempo_carga, self.capacidad_bateria, 
                    self.tipo_hibrido, self.consumo_mixto, self.imagen_url)
            cursor.execute(sql, params)
            conn.commit()
            self.id = cursor.lastrowid
        conn.close()

    @staticmethod
    def get_all():
        # Devuelve todos los coches de la base de datos
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, marca, modelo, precio, anyo, tipo, autonomia, en_oferta, "
                        "tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto, imagen_url FROM coches ORDER BY id DESC")
            rows = cursor.fetchall()
        conn.close()
        return [
            Coche(marca=row[1], modelo=row[2], precio=row[3], anyo=row[4], tipo=row[5].lower() if row[5] else "desconocido", 
                tiempo_carga=row[8], capacidad_bateria=row[9], tipo_hibrido=row[10], consumo_mixto=row[11], imagen_url=row[12], id=row[0])
            for row in rows
        ]


    # Método para buscar coches
    @staticmethod
    def search(marca=None, modelo=None, precio_max=None, anyo=None, tipo=None, autonomia_min=None, tiempo_carga_max=None, capacidad_bateria=None, tipo_hibrido=None, consumo_mixto_max=None):
        conn = get_mariadb_connection()
        filters, params = [], []

        if marca:
            filters.append("marca LIKE %s")
            params.append(f"%{marca}%")
        if modelo:
            filters.append("modelo LIKE %s")
            params.append(f"%{modelo}%")
        if precio_max:
            try:
                precio = float(precio_max)
                filters.append("precio <= %s")
                params.append(precio)
            except ValueError:
                pass  
        if anyo:
            try:
                anyo_int = int(anyo)
                filters.append("anyo = %s")
                params.append(anyo_int)
            except ValueError:
                pass
        if tipo:
            tipo = tipo.lower()
            filters.append("tipo = %s")
            params.append(tipo)

        # Filtros avanzados SOLO si el tipo corresponde
        if tipo == "electrico":
            if autonomia_min:
                filters.append("autonomia >= %s")
                params.append(float(autonomia_min))
            if tiempo_carga_max:
                filters.append("tiempo_carga <= %s")
                params.append(float(tiempo_carga_max))
            if capacidad_bateria:
                filters.append("capacidad_bateria >= %s")
                params.append(float(capacidad_bateria))
        elif tipo == "hibrido":
            if autonomia_min:
                filters.append("autonomia >= %s")
                params.append(float(autonomia_min))
            if tipo_hibrido:
                filters.append("tipo_hibrido = %s")
                params.append(tipo_hibrido)
            if consumo_mixto_max:
                filters.append("consumo_mixto <= %s")
                params.append(float(consumo_mixto_max))

        query = ("SELECT id, marca, modelo, precio, anyo, tipo, autonomia, en_oferta, "
                "tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto FROM coches")
        if filters:
            query += " WHERE " + " AND ".join(filters)

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        conn.close()

        return [
            Coche(
                marca=row[1], modelo=row[2], precio=row[3], anyo=row[4], tipo=row[5].lower() if row[5] else "desconocido", 
                en_oferta=bool(row[7]), tiempo_carga=row[8], capacidad_bateria=row[9], 
                tipo_hibrido=row[10], consumo_mixto=row[11], id=row[0]
            )
            for row in rows
        ]


# Decorador para rutas que requieren autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function



# === Rutas de Flask ===


# === Ruta de inicio ===

@app.route("/")
def index():
    return render_template("index.html", active_page="index")

# Funciones para el historial de precios
def obtener_historial_precios(coche_id):
    historial = historial_precios_col.find_one({"coche_id": coche_id})
    return historial["precios"] if historial and "precios" in historial else []

def guardar_historial_precio(coche_id, nuevo_precio):
    result = historial_precios_col.update_one(
        {"coche_id": int(coche_id)},
        {"$push": {
            "precios": {
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "precio": nuevo_precio
            }
        }},
        upsert=True
    )


# === Ruta de anuncios con filtros avanzados ===

@app.route('/anuncios', methods=['GET'])
def anuncios():
    marca = request.args.get("marca")
    modelo = request.args.get("modelo")
    precio_max = request.args.get("precio_max")
    anyo = request.args.get("anyo")
    tipo = request.args.get("tipo")

    # Recoge los nuevos filtros avanzados
    autonomia_min_electrico = request.args.get("autonomia_min_electrico")
    autonomia_min_hibrido = request.args.get("autonomia_min_hibrido")
    tiempo_carga_max = request.args.get("tiempo_carga_max")
    capacidad_bateria = request.args.get("capacidad_bateria")
    tipo_hibrido = request.args.get("tipo_hibrido")
    consumo_mixto_max = request.args.get("consumo_mixto_max")

    # Construir la consulta SQL
    query = ("SELECT id, marca, modelo, precio, anyo, tipo, autonomia, en_oferta, "
             "tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto, imagen_url FROM coches WHERE 1=1")
    params = []

    if marca:
        query += " AND marca = %s"
        params.append(marca)
    if modelo:
        query += " AND modelo = %s"
        params.append(modelo)
    if precio_max:
        query += " AND precio <= %s"
        params.append(precio_max)
    if anyo:
        query += " AND anyo = %s"
        params.append(anyo)
    if tipo:
        query += " AND tipo = %s"
        params.append(tipo)

        # Filtros avanzados SOLO si el tipo corresponde
        if tipo == "electrico":
            if autonomia_min_electrico:
                query += " AND autonomia >= %s"
                params.append(autonomia_min_electrico)
            if tiempo_carga_max:
                query += " AND tiempo_carga <= %s"
                params.append(tiempo_carga_max)
            if capacidad_bateria:
                query += " AND capacidad_bateria >= %s"
                params.append(capacidad_bateria)
        elif tipo == "hibrido":
            if autonomia_min_hibrido:
                query += " AND autonomia >= %s"
                params.append(autonomia_min_hibrido)
            if tipo_hibrido:
                query += " AND tipo_hibrido = %s"
                params.append(tipo_hibrido)
            if consumo_mixto_max:
                query += " AND consumo_mixto <= %s"
                params.append(consumo_mixto_max)

    query += " ORDER BY id DESC"

    # Ejecuta la consulta y obtiene los coches filtrados
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
    conn.close()

    coches = [
        Coche(id=row[0], marca=row[1], modelo=row[2], precio=row[3], anyo=row[4], tipo=row[5].lower() if row[5] else "desconocido", autonomia=row[6], 
              en_oferta=bool(row[7]), tiempo_carga=row[8], capacidad_bateria=row[9], 
              tipo_hibrido=row[10], consumo_mixto=row[11], imagen_url=row[12])
        for row in rows
    ]

    # Obtener el historial de precios de MongoDB
    historial_por_coche = {coche.id: obtener_historial_precios(coche.id) for coche in coches}

    comentarios_por_anuncio = {}
    for coche in coches:
        comentarios = list(comentarios_col.find({"coche_id": coche.id}))
        comentarios_con_nombres = []

        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            for comentario in comentarios:
                cursor.execute("SELECT nombre FROM usuarios WHERE id = %s", (comentario.get("usuario_id"),))
                usuario = cursor.fetchone()
                nombre_usuario = usuario[0] if usuario else "Usuario desconocido"

                comentarios_con_nombres.append({
                    "nombre_usuario": nombre_usuario,
                    "texto": comentario.get("comentario", "Comentario no disponible"),
                    "fecha": comentario.get("fecha", "Fecha desconocida")
                })
        conn.close()

        comentarios_por_anuncio[coche.id] = comentarios_con_nombres

    return render_template("anuncios.html", anuncios=coches, comentarios_por_anuncio=comentarios_por_anuncio, historial_por_coche=historial_por_coche, active_page="anuncios")





# == Editar anuncio ==

@app.route('/editar_anuncio/<int:coche_id>', methods=['GET', 'POST'])
def editar_anuncio(coche_id):
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT marca, modelo, tipo, precio, anyo, autonomia, tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto FROM coches WHERE id = %s", (coche_id,))
        coche = cursor.fetchone()
    conn.close()

    if request.method == "POST":
        nuevo_tipo = request.form.get("tipo")
        nuevo_precio = request.form.get("precio")
        nuevo_anyo = request.form.get("anyo")
        nueva_autonomia = request.form.get("autonomia") if nuevo_tipo in ["hibrido", "electrico"] else None
        nuevo_tiempo_carga = request.form.get("tiempo_carga") if nuevo_tipo == "electrico" else None
        nueva_capacidad_bateria = request.form.get("capacidad_bateria") if nuevo_tipo == "electrico" else None
        nuevo_tipo_hibrido = request.form.get("tipo_hibrido") if nuevo_tipo == "hibrido" else None
        nuevo_consumo_mixto = request.form.get("consumo_mixto") if nuevo_tipo == "hibrido" else None


        # Verificar que el precio es válido antes de guardarlo en Mongo
        if nuevo_precio and nuevo_precio.isdigit():
            nuevo_precio = int(nuevo_precio)

            # Actualizar los datos del coche en MariaDB
            conn = get_mariadb_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE coches 
                    SET tipo = %s, precio = %s, anyo = %s, autonomia = %s, tiempo_carga = %s, capacidad_bateria = %s, tipo_hibrido = %s, consumo_mixto = %s
                    WHERE id = %s
                """, (nuevo_tipo, nuevo_precio, nuevo_anyo, nueva_autonomia, nuevo_tiempo_carga, nueva_capacidad_bateria, nuevo_tipo_hibrido, nuevo_consumo_mixto, coche_id))
                conn.commit()
            conn.close()

            # Guardar el historial de precios en MongoDB
            guardar_historial_precio(coche_id, nuevo_precio)

            flash("Anuncio actualizado correctamente", "success")
        else:
            flash("El precio debe ser un número válido", "danger")

        return redirect(url_for("ventas"))

    return render_template("editar_anuncio.html", coche=coche)


# === Eliminar anuncio ==

@app.route('/borrar_anuncio/<int:coche_id>', methods=['POST'])
def borrar_anuncio(coche_id):
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM coches WHERE id = %s", (coche_id,))
        conn.commit()
    conn.close()

    flash("Anuncio eliminado correctamente", "success")
    return redirect(url_for("ventas"))


# === Ruta registro usuarios ===

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        password = request.form["password"]
        tipo_usuario = request.form["tipo_usuario"]

        # Hash de la contraseña
        hashed_password = generate_password_hash(password)

        # Guardar el usuario en la base de datos
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (nombre, email, tipo_usuario, password) VALUES (%s, %s, %s, %s)",
                (nombre, email, tipo_usuario, hashed_password)
            )
            conn.commit()
        conn.close()

        flash("Registro exitoso. Puedes iniciar sesión.")
        return redirect(url_for("login"))

    return render_template("registro.html")



# === Ruta de inicio de sesión ===

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nombre, email, password FROM usuarios WHERE email = %s", (email,))
            usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario[3], password):
            session["user_id"] = usuario[0]
            session["nombre"] = usuario[1]
            session["email"] = usuario[2]
            return redirect(url_for("index"))
        else:
            flash("Credenciales incorrectas.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))



# === Rutas de Publicaciones ===

@app.route("/publicar", methods=["GET", "POST"])
@login_required
def publicar():
    if request.method == "POST":
        # Capturar los datos del usuario autenticado
        nombre_vendedor = session.get("nombre")
        email_vendedor = session.get("email")
        
        if not nombre_vendedor or not email_vendedor:
            flash("Error: No se han encontrado los datos del vendedor.")
            return redirect(url_for("publicar"))

        # Capturar los datos del coche
        coche = Coche.from_form(request.form)
        tiempo_carga = request.form.get("tiempo_carga") if coche.tipo == "electrico" else None
        capacidad_bateria = request.form.get("capacidad_bateria") if coche.tipo == "electrico" else None
        tipo_hibrido = request.form.get("tipo_hibrido") if coche.tipo == "hibrido" else None
        consumo_mixto = request.form.get("consumo_mixto") if coche.tipo == "hibrido" else None


        # Guardar las imágenes
        imagenes_guardadas = []
        if "imagenes" in request.files:
            archivos = request.files.getlist("imagenes")
            for archivo in archivos:
                if archivo.filename != "":
                    filename = secure_filename(archivo.filename)
                    archivo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    imagenes_guardadas.append("images/" + filename)  # 🔹 Guardamos la ruta relativa correcta
                    print(imagenes_guardadas)  # 🔹 Verifica que las imágenes tienen "images/nombre.jpg"



        # Guardar el coche en la base de datos y asociarlo con el usuario
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            sql = ("INSERT INTO coches (marca, modelo, precio, anyo, tipo, autonomia, en_oferta, vendedor_id, tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto, imagen_url) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            params = (coche.marca, coche.modelo, coche.precio, coche.anyo, coche.tipo, coche.autonomia, 
                      int(coche.en_oferta), session["user_id"], tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto, ",".join(imagenes_guardadas))
            cursor.execute(sql, params)
            conn.commit()

        conn.close()
        return redirect(url_for("anuncios"))

    return render_template("publicar.html", active_page="publicar")


# === Ruta de búsqueda ===

@app.route("/buscar", methods=["GET"])
def buscar():
    marca = request.args.get("marca")
    modelo = request.args.get("modelo")
    precio_max = request.args.get("precio_max")
    anyo = request.args.get("anyo")
    tipo = request.args.get("tipo")

    resultados = Coche.search(marca, modelo, precio_max, anyo, tipo)
    return render_template("buscar.html", anuncios=resultados)



# === Rutas de comentarios ===

@app.route('/agregar_comentario/<int:coche_id>', methods=['POST'])
@login_required
def agregar_comentario(coche_id):
    usuario_id = session.get("user_id")
    comentario = request.form.get("comentario", "").strip()
    if not comentario:
        flash("El comentario no puede estar vacío.", "error")
        return redirect(url_for("anuncios"))

    # Verificar si el usuario ha comprado este coche
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM transacciones WHERE comprador_id = %s AND coche_id = %s", (usuario_id, coche_id))
        ha_comprado = cursor.fetchone()[0] > 0
    conn.close()

    if not ha_comprado:
        flash("Solo los compradores pueden dejar comentarios.", "error")
        return redirect(url_for("anuncios"))

    nuevo_comentario = {
        "usuario_id": usuario_id,
        "comentario": comentario,
        "fecha": datetime.now().strftime("%Y-%m-%d")
    }

    # Agregar el comentario al coche correspondiente en MongoDB
    comentarios_col.insert_one({
    "coche_id": coche_id,
    "usuario_id": usuario_id,
    "comentario": comentario,
    "fecha": datetime.now()
    })

    return redirect(url_for("anuncios"))



# === Rutas de favoritos ===

@app.route('/favoritos', methods=['GET'])
@login_required
def favoritos():
    user_id = session.get("user_id")  # Aquí obtenemos el user_id de la sesión

    favorito = favoritos_col.find_one({'user_id': str(user_id)})
    coches_ids = favorito.get('coches', []) if favorito else []

    coches_favoritos = []
    if coches_ids:
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            formato_ids = ','.join(['%s'] * len(coches_ids))
            query = (f"SELECT id, marca, modelo, precio, anyo, tipo, autonomia, en_oferta, "
                     f"tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto "
                     f"FROM coches WHERE id IN ({formato_ids})")
            cursor.execute(query, coches_ids)
            rows = cursor.fetchall()
            coches_favoritos = [
                Coche(marca=row[1], modelo=row[2], precio=row[3], anyo=row[4],
                      tipo=row[5].lower() if row[5] else "desconocido", autonomia=row[6], en_oferta=bool(row[7]),
                      tiempo_carga=row[8], capacidad_bateria=row[9], 
                      tipo_hibrido=row[10], consumo_mixto=row[11], id=row[0])
                for row in rows
            ]
        conn.close()

    return render_template('favoritos.html', anuncios=coches_favoritos, active_page="favoritos")



# === Añadir un coche a favoritos ===
@app.route('/añadir_favorito', methods=['POST'])
@login_required
def añadir_favorito():
    anuncio_id = int(request.form.get('anuncio_id'))
    user_id = session.get("user_id")

    favorito = favoritos_col.find_one({'user_id': str(user_id)})

    if favorito:
        if anuncio_id not in favorito['coches']:
            favoritos_col.update_one(
                {'user_id': str(user_id)},
                {'$push': {'coches': anuncio_id}}
            )
    else:
        favoritos_col.insert_one({
            'user_id': str(user_id),
            'coches': [anuncio_id]
        })

    flash("Anuncio añadido a favoritos.")
    return redirect(url_for('favoritos'))


# === Eliminar un coche de favoritos ===

@app.route('/eliminar_favorito/<int:anuncio_id>', methods=['POST'])
@login_required
def eliminar_favorito(anuncio_id):
    user_id = session.get("user_id")
    
    favoritos_col.update_one(
        {'user_id': str(user_id)},
        {'$pull': {'coches': anuncio_id}}
    )
    
    flash("Anuncio eliminado de favoritos.")
    return redirect(url_for('favoritos'))




# === Rutas de oferta ===

@app.route('/hacer_oferta/<int:anuncio_id>', methods=['GET', 'POST'])
@login_required
def hacer_oferta(anuncio_id):
    if request.method == 'POST':
        # Obtener el vendedor asociado a este anuncio desde la base de datos SQL
        conn = get_mariadb_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT vendedor_id FROM coches WHERE id = %s", (anuncio_id,))
            vendedor = cursor.fetchone()
        conn.close()
        if not vendedor:
            flash("El anuncio no existe.", "error")
            return redirect(url_for('anuncios'))

        oferta = {
            'coche_id': anuncio_id,
            'user_id': session.get('user_id'),
            'nombre_usuario': session.get('nombre'),
            'monto': float(request.form['monto']),
            'mensaje': request.form['mensaje'],
            'estado': "pendiente",  # Estado por defecto
            'vendedor_id': vendedor[0]  # ID del vendedor obtenido desde MariaDB
        }

        ofertas_col.insert_one(oferta)
        flash('Oferta enviada correctamente!')  # Mostrar mensaje (extra)
        return redirect(url_for('anuncios'))

    return render_template('hacer_oferta.html', anuncio_id=anuncio_id)



    # Aceptar oferta

@app.route('/aceptar_oferta/<string:oferta_id>', methods=['POST'])
@login_required
def aceptar_oferta(oferta_id):
    oferta = ofertas_col.find_one({'_id': ObjectId(oferta_id)})
    if not oferta:
        flash("Oferta no encontrada", "error")
        return redirect(url_for("ventas"))

    if oferta["vendedor_id"] != session.get("user_id"):
        flash("No tienes permisos para aceptar esta oferta", "error")
        return redirect(url_for("ventas"))

    # Actualizar estado de la oferta en MongoDB
    ofertas_col.update_one({"_id": ObjectId(oferta_id)}, {"$set": {"estado": "aceptada"}})

    # Registrar la transacción en MariaDB
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO transacciones (comprador_id, vendedor_id, coche_id, precio_final) VALUES (%s, %s, %s, %s)",
                       (oferta["user_id"], oferta["vendedor_id"], oferta["coche_id"], oferta["monto"]))
        conn.commit()
    conn.close()
    flash("Oferta aceptada y venta registrada correctamente.")
    return redirect(url_for("ventas"))




# Rechazar oferta

@app.route('/rechazar_oferta/<string:oferta_id>', methods=['POST'])
@login_required
def rechazar_oferta(oferta_id):
    oferta = ofertas_col.find_one({'_id': ObjectId(oferta_id)})
    if not oferta:
        flash("Oferta no encontrada", "error")
        return redirect(url_for("ventas"))

    if oferta["vendedor_id"] != session.get("user_id"):
        flash("No tienes permisos para rechazar esta oferta", "error")
        return redirect(url_for("ventas"))

    ofertas_col.update_one({"_id": ObjectId(oferta_id)}, {"$set": {"estado": "rechazada"}})

    flash("Oferta rechazada correctamente.")
    return redirect(url_for("ventas"))



# === Ruta ventas ===

@app.route('/ventas', methods=['GET'])
@login_required
def ventas():
    user_id = session.get("user_id")
    if not user_id:
        flash("Error: No se ha encontrado el usuario.", "error")
        return redirect(url_for("login"))

    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, marca, modelo, precio, anyo, tipo, autonomia, en_oferta, tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto FROM coches WHERE vendedor_id = %s", (user_id,))
        rows = cursor.fetchall()
    conn.close()

    coches_vendidos = [
        Coche(marca=row[1], modelo=row[2], precio=row[3], anyo=row[4], tipo=row[5].lower() if row[5] else "desconocido", autonomia=row[6], en_oferta=bool(row[7]), 
              tiempo_carga=row[8], capacidad_bateria=row[9], tipo_hibrido=row[10], consumo_mixto=row[11], id=row[0])
        for row in rows
    ]

    # Obtener ofertas de MongoDB asociadas a los coches del vendedor
    ofertas_por_coche = {}
    for coche in coches_vendidos:
        ofertas = list(ofertas_col.find({"coche_id": int(coche.id)}))
        for oferta in ofertas:
            oferta["_id"] = str(oferta["_id"])
        ofertas_por_coche[coche.id] = ofertas

    return render_template('ventas.html', anuncios=coches_vendidos, ofertas_por_coche=ofertas_por_coche, active_page="ventas")



# === Ruta de mis compras ===

@app.route('/mis_compras', methods=['GET'])
@login_required
def mis_compras():
    usuario_id = session.get("user_id")

    # Obtener las compras del usuario desde MariaDB
    conn = get_mariadb_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT coches.id, coches.marca, coches.modelo, transacciones.precio_final, transacciones.fecha_venta, 
                   coches.tipo, coches.autonomia, coches.tiempo_carga, coches.capacidad_bateria, coches.tipo_hibrido, coches.consumo_mixto
            FROM transacciones 
            JOIN coches ON transacciones.coche_id = coches.id 
            WHERE transacciones.comprador_id = %s
        """, (usuario_id,))
        compras = cursor.fetchall()
    conn.close()

    # Transformar las compras en un diccionario con nuevos datos
    coches_comprados = []
    for compra in compras:
        coche_id, marca, modelo, precio, fecha, tipo, autonomia, tiempo_carga, capacidad_bateria, tipo_hibrido, consumo_mixto = compra
        coches_comprados.append({
            "marca": marca,
            "modelo": modelo,
            "precio": precio,
            "fecha": fecha,
            "tipo": tipo,
            "autonomia": autonomia,
            "tiempo_carga": tiempo_carga,
            "capacidad_bateria": capacidad_bateria,
            "tipo_hibrido": tipo_hibrido,
            "consumo_mixto": consumo_mixto,
            "coche_id": coche_id
        })

    return render_template("mis_compras.html", compras=coches_comprados, active_page="mis_compras")


# === Ejecucion del programa ===

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)