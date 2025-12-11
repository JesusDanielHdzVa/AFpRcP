import io
import base64
import os

import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, jsonify 
from flask_sqlalchemy import SQLAlchemy
import json
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

# Configuración de Cloudinary
cloudinary.config( 
  cloud_name = "dbb1msq4h", 
  api_key = "841264353244837", 
  api_secret = "qMKjBB3JAkWZ0Ogs1vEdKxfowww",
  secure = True
)

app = Flask(__name__)

database_url = os.environ.get('DATABASE_URL', 'sqlite:///robotics.db')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'robot_images')
db = SQLAlchemy(app)

# Configura tu API Key de Gemini
GENAI_API_KEY = "AIzaSyCNMH0akbwwhI_tqeB7V6wEwANas7HzXR0" 
genai.configure(api_key=GENAI_API_KEY)

# --- MODELOS DE BASE DE DATOS ---
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) 

class RobotImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_number = db.Column(db.String(50), nullable=False) 
    url = db.Column(db.Text, nullable=False)
    
class PitData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_number = db.Column(db.String(50), nullable=False)
    drivetrain = db.Column(db.String(50))
    intake = db.Column(db.String(50))
    pit_comments = db.Column(db.Text)
    robot_image = db.Column(db.Text, nullable=True) 
    
class MatchData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_number = db.Column(db.String(50), nullable=False)
    match_number = db.Column(db.Integer) 
    
    points_scored = db.Column(db.Integer)
    has_failed = db.Column(db.Boolean)
    
    auto_moved = db.Column(db.Boolean) 
    endgame_result = db.Column(db.String(20))
    played_defense = db.Column(db.Boolean) 
    comments = db.Column(db.Text) 
    
    score_data = db.Column(db.Text, nullable=True) 
    fail_data = db.Column(db.Text, nullable=True)

with app.app_context():
    db.create_all()

# --- CLASE DE ANÁLISIS ---
class TeamAnalytics:
    def __init__(self, team_name):
        self.team_name = team_name
        self.pit_data = PitData.query.filter_by(team_number=team_name).first()
        self.matches = MatchData.query.filter_by(team_number=team_name).order_by(MatchData.match_number).all()
        
        self.images_objs = RobotImage.query.filter_by(team_number=team_name).all()
        self.images_list = [img.url for img in self.images_objs]

        self.total_matches = len(self.matches)
        self.total_points = sum(m.points_scored for m in self.matches) if self.matches else 0
        self.avg_points = round(self.total_points / self.total_matches, 2) if self.total_matches > 0 else 0
        
        # 1. Autónomo
        self.auto_count = sum(1 for m in self.matches if m.auto_moved)
        self.auto_percent = round((self.auto_count / self.total_matches * 100), 1) if self.total_matches > 0 else 0
        
        # 2. Defensa
        self.defense_count = sum(1 for m in self.matches if m.played_defense)
        self.defense_percent = round((self.defense_count / self.total_matches * 100), 1) if self.total_matches > 0 else 0
        
        # 3. Fallos
        self.fail_count = sum(1 for m in self.matches if m.has_failed)

        # 4. Climb
        self.climb_count = sum(1 for m in self.matches if m.endgame_result == 'Climb')

    def get_kpis(self):
        if not self.matches:
            return None
        return {
            "avg_points": self.avg_points,
            "max_points": max((m.points_scored for m in self.matches), default=0),
            "total_matches": self.total_matches,
            "auto_rate": f"{self.auto_percent}%",
            "defense_rate": f"{self.defense_percent}%",
            "climb_count": self.climb_count
        }

    def generate_all_graphs(self):
        if not self.matches:
            return None, None, None

        # --- 1. PROCESAMIENTO DE DATOS ---
        match_nums = [m.match_number for m in self.matches]
        points = [m.points_scored for m in self.matches]
        
        all_score_x = []
        all_score_y = []
        all_fail_x = []
        all_fail_y = []

        for m in self.matches:
            if m.score_data:
                try:
                    shots = json.loads(m.score_data) 
                    for shot in shots:
                        all_score_x.append(shot['x'])
                        all_score_y.append(shot['y'])
                except:
                    pass

            if m.fail_data:
                try:
                    fails = json.loads(m.fail_data)
                    for f in fails:
                        all_fail_x.append(f['x'])
                        all_fail_y.append(f['y'])
                except:
                    pass

        # --- HELPER BASE64 ---
        def fig_to_base64(fig):
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight', transparent=True)
            img.seek(0)
            plt.close(fig)
            return base64.b64encode(img.getvalue()).decode()

        # --- GRÁFICA A: MAPA DE TIROS ---
        fig1, ax1 = plt.subplots(figsize=(12, 7))
        
        try:
            img_path = os.path.join(app.root_path, 'static', 'FRC2025.png')
            if os.path.exists(img_path):
                img = mpimg.imread(img_path)
                ax1.imshow(img, extent=[0, 100, 100, 0])
        except Exception as e:
            print(f"Error imagen: {e}")

        if all_score_x:
            ax1.scatter(all_score_x, all_score_y, c='#28a745', label='Anotación', alpha=0.7, s=120, edgecolors='white')

        if all_fail_x:
            ax1.scatter(all_fail_x, all_fail_y, c='#dc3545', marker='x', label='Fallo', alpha=0.9, s=120, linewidths=3)

        ax1.set_title(f"Mapa de Tiros ({len(all_score_x)} disparos) - {self.team_name}", fontsize=18)
        ax1.set_xlim(0, 100)
        ax1.set_ylim(100, 0)
        ax1.legend(loc='upper right', fontsize=12)
        ax1.axis('off')
        
        img_map = fig_to_base64(fig1)

        # --- GRÁFICA B: TENDENCIA ---
        fig3, ax3 = plt.subplots(figsize=(6, 4))
        ax3.plot(match_nums, points, marker='o', linestyle='-', color='#004d99', linewidth=2)
        ax3.set_title('Progreso de Puntos')
        ax3.set_xlabel('Match')
        ax3.grid(True, linestyle='--', alpha=0.6)
        img_trend = fig_to_base64(fig3)

        # --- GRÁFICA C: ENDGAME (PASTEL) ---
        endgame_counts = {}
        for m in self.matches:
            res = str(m.endgame_result) if m.endgame_result else "Ninguno"
            endgame_counts[res] = endgame_counts.get(res, 0) + 1
            
        fig4, ax4 = plt.subplots(figsize=(6, 4))
        
        if endgame_counts:
            valores = list(endgame_counts.values())
            etiquetas = list(endgame_counts.keys())
            colores = ['#ff9999','#66b3ff','#99ff99', '#ffcc99', '#c2c2f0']
            ax4.pie(valores, labels=etiquetas, autopct='%1.1f%%', startangle=90, colors=colores)
            ax4.set_title('Resultados Endgame')
        else:
            ax4.text(0.5, 0.5, "Sin datos de Endgame", ha='center', va='center')
            ax4.axis('off')

        img_endgame = fig_to_base64(fig4)

        return img_map, img_trend, img_endgame
    
    # --- AI ---
    def ask_ai_summary(self):
        if not self.matches:
            return "No hay datos."
            
        todos_comentarios = " | ".join([m.comments for m in self.matches if m.comments])
        
        contexto = f"""
        Eres un estratega de FRC. Analiza al equipo {self.team_name}.
        Partidos jugados: {self.total_matches}.
        Promedio Puntos Teleop: {self.avg_points}.
        
        Autónomo (Movimiento): {self.auto_count}/{self.total_matches} veces.
        Endgame (Climb): {self.climb_count}/{self.total_matches} veces.
        
        Jugó defensa: {self.defense_count} veces.
        Fallos técnicos: {self.fail_count}.
        Comentarios de los scouters: "{todos_comentarios}".
        
        Dime: 1. Sus fortalezas. 2. Sus debilidades. 3. ¿Sirve para alianza? (Breve). 4.Resumen de los comentarios.
        Evita usar bolds o viñetas complejas, solo texto plano.
        """
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(contexto)
            return response.text
        except Exception as e:
            return f"Error IA: {str(e)}"

# --- RUTAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_team', methods=['GET', 'POST'])
def add_team():
    if request.method == 'POST':
        team_name = request.form.get('team_name').upper().strip()
        existe = Team.query.filter_by(name=team_name).first()
        if not existe and team_name:
            nuevo_equipo = Team(name=team_name)
            db.session.add(nuevo_equipo)
            db.session.commit()
        return redirect(url_for('add_team'))

    equipos_registrados = Team.query.all()
    return render_template('add_team.html', teams=equipos_registrados)

@app.route('/scouting', methods=['GET', 'POST'])
def scouting():
    if request.method == 'POST':
        form_type = request.form.get('scouting_type')
        team_name = request.form.get('team_name')

        if form_type == 'pit':
            # 1. Buscar datos viejos para preservar la imagen si no se sube una nueva
            datos_viejos = PitData.query.filter_by(team_number=team_name).first()
            old_image_url = datos_viejos.robot_image if datos_viejos else None

            drivetrain = request.form.get('drivetrain')
            intake = request.form.get('intake_type')
            pit_comments = request.form.get('pit_comments')
            
            new_image_url = None
            
            # 2. Intentar subir imagen nueva
            if 'robot_image' in request.files:
                file = request.files['robot_image']
                if file and file.filename != '':
                    try:
                        upload_result = cloudinary.uploader.upload(file, folder="frc_scouting")
                        new_url = upload_result["secure_url"]
                        
                        # Guardamos en la NUEVA tabla (acumulativo)
                        nueva_foto = RobotImage(team_number=team_name, url=new_url)
                        db.session.add(nueva_foto)
                    except Exception as e:
                        print(f"Error imagen: {e}")

            # Guardamos los datos de texto (PitData ya no lleva imagen)
            nuevo_pit = PitData(
                team_number=team_name,
                drivetrain=drivetrain,
                intake=intake,
                pit_comments=pit_comments
            )
            PitData.query.filter_by(team_number=team_name).delete()
            db.session.add(nuevo_pit)
            db.session.commit()
            print(f"PIT Guardado para {team_name}")

        elif form_type == 'match':
            try:
                match_num = int(request.form.get('match_number', 0))
                points = int(request.form.get('points', 0))
            except ValueError:
                match_num = 0
                points = 0

            auto_moved = True if request.form.get('auto_moved') == 'yes' else False
            has_failed = True if request.form.get('has_failed') == 'yes' else False
            played_defense = True if request.form.get('played_defense') == 'yes' else False
            endgame_result = request.form.get('endgame_result')
            comments = request.form.get('comments')
            
            score_data_json = request.form.get('score_data')
            fail_data_json = request.form.get('fail_data')

            nuevo_match = MatchData(
                team_number = team_name,
                match_number = match_num,
                points_scored = points,
                auto_moved = auto_moved,
                has_failed = has_failed,
                played_defense = played_defense,
                endgame_result = endgame_result,
                comments = comments,
                score_data = score_data_json,
                fail_data = fail_data_json
            )

            db.session.add(nuevo_match)
            db.session.commit()
            
        return redirect(url_for('scouting'))

    equipos_disponibles = Team.query.all() 
    return render_template('scouting.html', teams=equipos_disponibles)

@app.route('/data', methods=['GET', 'POST'])
def data():
    kpis = None
    graphs = (None, None, None) 
    team_searched = ""
    matches_list = []
    equipo_obj = None 
    
    equipos_disponibles = Team.query.all()

    if request.method == 'POST':
        team_searched = request.form.get('team_search') 
        
        if team_searched:
            equipo_obj = TeamAnalytics(team_searched)
            kpis = equipo_obj.get_kpis()
            graphs = equipo_obj.generate_all_graphs() 
            matches_list = equipo_obj.matches

    return render_template('data.html', 
                           kpis=kpis, 
                           graphs=graphs,
                           matches=matches_list,
                           team=team_searched,
                           equipo_obj=equipo_obj, 
                           teams=equipos_disponibles)

@app.route('/api/ask_ai', methods=['POST'])
def ask_ai_endpoint():
    data = request.get_json()
    team_name = data.get('team')
    
    if not team_name:
        return jsonify({'response': 'Error: No se seleccionó equipo.'})

    equipo_obj = TeamAnalytics(team_name)
    respuesta = equipo_obj.ask_ai_summary()
    
    return jsonify({'response': respuesta})

'''@app.route('/reset_total')
def reset_db():
    try:
        db.drop_all()  
        db.create_all() 
        return "Base de datos reseteada desde cero. Estructura actualizada."
    except Exception as e:
        return f"Error: {str(e)}"'''

if __name__ == '__main__':
    app.run(debug=True)