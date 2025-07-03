from flask import Flask, jsonify, request, session, flash # type: ignore
from flask_cors import CORS # type: ignore
import numpy as np # type: ignore
import tflite_runtime.interpreter as tflite # type: ignore
import psycopg2 # type: ignore
from datetime import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
#CORS(app, supports_credentials=True)
CORS(app, resources={r"/api/*": {"origins": "https://frontend-semana13.netlify.app"}}, supports_credentials=True)

# CORS(app, origins='FRONTEND_URL', supports_credentials=True)

app.secret_key = 'SECRET_KEY'

interpreter = None
input_details = None
output_details = None

def load_model():
    global interpreter, input_details, output_details
    if interpreter is None:
        try:
            model_path = os.path.join(os.path.dirname(__file__), "modeloDEC.tflite")
            if not os.path.exists(model_path):
                print("❌ modeloDEC.tflite no encontrado.")
                return False

            interpreter = tflite.Interpreter(model_path=model_path)
            interpreter.allocate_tensors()
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            print("✅ Modelo cargado correctamente.")
            return True
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            return False
    return True

def predict_with_tflite(input_data):
    if not load_model():
        raise RuntimeError("Modelo no disponible")
    input_data = input_data.astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details[0]['index'])
    return output_data[0]


def get_db_connection():
    return psycopg2.connect('postgresql://db_unfv_ver5_user:rTxeXCWafkztYkNnhrRPZCnBIqATGP1c@dpg-d13fbvk9c44c7399ca1g-a.oregon-postgres.render.com/db_unfv_ver5')
    return psycopg2.connect(os.getenv('DATABASE_URL'))
    #internal_db_url = postgresql://db_unfv_ver5_user:rTxeXCWafkztYkNnhrRPZCnBIqATGP1c@dpg-d13fbvk9c44c7399ca1g-a/db_unfv_ver5
    #external_db_url = postgresql://db_unfv_ver5_user:rTxeXCWafkztYkNnhrRPZCnBIqATGP1c@dpg-d13fbvk9c44c7399ca1g-a.oregon-postgres.render.com/db_unfv_ver5

@app.route('/api/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, username, tipo 
        FROM usuarios 
        WHERE username = %s AND password = %s
    """, (username, password))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        session['logged_in'] = True
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['user_type'] = user[2]
        return jsonify({'message': 'Inicio de sesión exitoso', 'user_type': user[2]}), 200
    else:
        return jsonify({'message': 'Usuario o contraseña incorrectos'}), 401

@app.route('/api/registro', methods=['POST'])
def registro():
    username = request.json.get('username')
    password = request.json.get('password')
    tipo = 'paciente'
    nombre = request.json.get('nombre')
    apellido = request.json.get('apellido') 
    fecha_nacimiento = request.json.get('fecha_nacimiento')
    genero = request.json.get('genero')
    telefono = request.json.get('telefono')
    direccion = request.json.get('direccion')
    dni = request.json.get('dni')

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO usuarios (
                username, password, tipo,
                nombre, apellido, fecha_nacimiento,
                genero, telefono, direccion, dni
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            username, password, tipo,
            nombre, apellido, fecha_nacimiento,
            genero, telefono, direccion, dni
        ))

        conn.commit()
        return jsonify({'message': 'Registro exitoso. Ahora puede iniciar sesión.'}), 201

    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'message': 'El nombre de usuario o DNI ya existe'}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'Error en el registro: {str(e)}'}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout exitoso'}), 200

@app.route('/api/diagnostico', methods=['POST'])
def diagnostico():
    if not session.get('logged_in'):
        return jsonify({'message': 'Unauthorized'}), 401

    try:
        edad = int(request.json.get('edad'))
        genero = request.json.get('genero')
        ps = int(request.json.get('ps'))
        pd = int(request.json.get('pd'))
        col = float(request.json.get('colesterol'))
        glu = float(request.json.get('glucosa'))
        fuma = request.json.get('fuma')
        alcohol = request.json.get('alcohol')
        actividad = request.json.get('actividad')
        peso = float(request.json.get('peso'))
        estatura = int(request.json.get('estatura'))

        imc = peso / ((estatura / 100) ** 2)

        entrada = [
            0 if edad < 45 else 1 if edad <= 59 else 2,
            0 if 'femenino' in genero.lower() else 1,
            0 if ps < 120 else 1 if ps <= 139 else 2,
            0 if pd < 80 else 1 if pd <= 89 else 2,
            0 if col < 200 else 1 if col <= 239 else 2,
            0 if glu < 100 else 1 if glu <= 125 else 2,
            1 if fuma == 's' else 0,
            1 if alcohol == 's' else 0,
            2 if 'no' in actividad.lower() else 1 if '1' in actividad or '2' in actividad else 0,
            1 if imc == 0 else 1 if imc < 18.5 else 0 if imc < 25 else 1 if imc < 30 else 2
        ]

        input_array = np.array([entrada], dtype=np.float32)
        pred = predict_with_tflite(input_array)

        riesgo = int(np.argmax(pred))
        confianza = float(np.max(pred))

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO diagnostico_datos (
                usuario_id, edad, genero, ps, pd, colesterol, glucosa,
                fuma, alcohol, actividad, peso, estatura, imc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            session['user_id'], edad, genero, ps, pd, col, glu,
            fuma, alcohol, actividad, peso, estatura, imc
        ))
        datos_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO diagnostico_resultados (
                datos_id, riesgo, confianza, notas
            ) VALUES (%s, %s, %s, %s)
        """, (
            datos_id, riesgo, confianza, None 
        ))

        conn.commit()

        session['ultimo_diagnostico'] = [
            riesgo,
            confianza,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]

        return jsonify({'riesgo': riesgo, 'confianza': confianza}), 200

    except Exception as e:
        return jsonify({'message': f'Error en el diagnóstico: {str(e)}'}), 500

    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@app.route('/api/resultados', methods=['GET'])
def resultados():
    if not session.get('logged_in'):
        return jsonify({'message': 'Unauthorized'}), 401
    
    diagnostico = None

    if 'ultimo_diagnostico' in session:
        riesgo, confianza, fecha_str = session['ultimo_diagnostico']
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d %H:%M:%S')
        diagnostico = {'riesgo': riesgo, 'confianza': confianza, 'fecha': fecha_str}
        session.pop('ultimo_diagnostico') 
    else:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
            SELECT r.riesgo, r.confianza, r.fecha_diagnostico 
            FROM diagnostico_resultados r
            JOIN diagnostico_datos d ON r.datos_id = d.id
            WHERE d.usuario_id = %s 
            ORDER BY r.fecha_diagnostico DESC 
            LIMIT 1
            """, (session['user_id'],))

            row = cur.fetchone()
            if row:
                diagnostico = {'riesgo': row[0], 'confianza': row[1], 'fecha': row[2]}
        except Exception as e:
            diagnostico = None
        finally:
            cur.close()
            conn.close()
    
    return jsonify({'diagnostico': diagnostico}), 200

@app.route('/api/admin', methods=['GET'])
def admin_panel():
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'message': 'Acceso no autorizado'}), 403

    filtro = request.args.get('filtro', '').lower()

    conn = get_db_connection()
    cur = conn.cursor()

    consulta = """
        SELECT u.id, u.username, u.nombre, u.apellido,
               COUNT(r.id) as total_diagnosticos,
               MAX(r.fecha_diagnostico) as ultimo_diagnostico
        FROM usuarios u
        LEFT JOIN diagnostico_datos d ON d.usuario_id = u.id
        LEFT JOIN diagnostico_resultados r ON r.datos_id = d.id
        WHERE u.tipo = 'paciente'
    """
    params = []

    if filtro:
        consulta += """
            AND (
                LOWER(u.username) LIKE %s OR
                LOWER(u.nombre) LIKE %s OR
                LOWER(u.apellido) LIKE %s
            )
        """
        like_pattern = f"%{filtro}%"
        params = [like_pattern, like_pattern, like_pattern]

    consulta += " GROUP BY u.id, u.username, u.nombre, u.apellido ORDER BY u.nombre"

    cur.execute(consulta, params)
    pacientes = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify({'pacientes': pacientes}), 200

@app.route('/api/admin/diagnosticos/<int:usuario_id>', methods=['GET'])
def ver_historial(usuario_id):
    if not session.get('logged_in') or session.get('user_type') != 'admin':
        return jsonify({'message': 'Acceso no autorizado'}), 403

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, username, nombre, apellido FROM usuarios WHERE id = %s", (usuario_id,))
    usuario = cur.fetchone()

    cur.execute("""
        SELECT 
            r.id, r.riesgo, r.confianza, r.fecha_diagnostico
        FROM diagnostico_resultados r
        JOIN diagnostico_datos d ON r.datos_id = d.id
        WHERE d.usuario_id = %s
        ORDER BY r.fecha_diagnostico DESC
    """, (usuario_id,))
    
    historial = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({'usuario': usuario, 'historial': historial}), 200

@app.route('/api/configuracion', methods=['GET', 'POST'])
def configuracion():
    if not session.get('logged_in'):
        return jsonify({'message': 'No autorizado'}), 401

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if request.method == 'GET':
            cur.execute("""
                SELECT nombre, apellido, fecha_nacimiento, genero, telefono, direccion, dni
                FROM usuarios
                WHERE id = %s
            """, (session['user_id'],))
            datos = cur.fetchone()
            if datos:
                campos = ['nombre', 'apellido', 'fecha_nacimiento', 'genero', 'telefono', 'direccion', 'dni']
                return jsonify(dict(zip(campos, datos))), 200
            else:
                return jsonify({'message': 'Usuario no encontrado'}), 404

        if request.method == 'POST':
            data = request.json
            cur.execute("""
                UPDATE usuarios
                SET nombre = %s, apellido = %s, fecha_nacimiento = %s,
                    genero = %s, telefono = %s, direccion = %s, dni = %s
                WHERE id = %s
            """, (
                data['nombre'], data['apellido'], data['fecha_nacimiento'],
                data['genero'], data['telefono'], data['direccion'], data['dni'],
                session['user_id']
            ))
            conn.commit()
            return jsonify({'message': 'Datos actualizados correctamente'}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'Error en la configuración: {str(e)}'}), 500

    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
