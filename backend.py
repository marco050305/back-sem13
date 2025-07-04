from flask import Flask, jsonify, request, session, flash  # type: ignore
from flask_cors import CORS  # type: ignore
import psycopg2  # type: ignore
from datetime import datetime
import os
import random

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://frontend-semana13.netlify.app"}}, supports_credentials=True)

app.secret_key = 'SECRET_KEY'

def get_db_connection():
    return psycopg2.connect('postgresql://db_unfv_ver5_user:rTxeXCWafkztYkNnhrRPZCnBIqATGP1c@dpg-d13fbvk9c44c7399ca1g-a.oregon-postgres.render.com/db_unfv_ver5')

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
        """, (username, password, tipo, nombre, apellido, fecha_nacimiento, genero, telefono, direccion, dni))
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

        # Predicción simulada
        riesgo = random.randint(0, 2)
        confianza = round(random.uniform(0.6, 0.9), 2)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO diagnostico_datos (
                usuario_id, edad, genero, ps, pd, colesterol, glucosa,
                fuma, alcohol, actividad, peso, estatura, imc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (session['user_id'], edad, genero, ps, pd, col, glu, fuma, alcohol, actividad, peso, estatura, imc))
        datos_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO diagnostico_resultados (
                datos_id, riesgo, confianza, notas
            ) VALUES (%s, %s, %s, %s)
        """, (datos_id, riesgo, confianza, 'Predicción simulada'))

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

# Resto de los endpoints (/api/resultados, /api/admin, etc.) permanecen igual
# No fueron modificados en esta limpieza del modelo

if __name__ == '__main__':
    app.run(debug=True, port=5000)
