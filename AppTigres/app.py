import io
import base64
import os
import matplotlib.image as mpimg
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, jsonify 
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///robotics.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
GENAI_API_KEY = "AIzaSyCNMH0akbwwhI_tqeB7V6wEwANas7HzXR0" 
genai.configure(api_key=GENAI_API_KEY)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) 

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
    
    fail_x = db.Column(db.Integer, nullable=True) 
    fail_y = db.Column(db.Integer, nullable=True)
    score_x = db.Column(db.Integer, nullable=True)
    score_y = db.Column(db.Integer, nullable=True)

with app.app_context():
    db.create_all()

class TeamAnalytics:
    def __init__(self, team_name):
        self.team_name = team_name
        self.matches = MatchData.query.filter_by(team_number=team_name).order_by(MatchData.match_number).all()
        
        self.total_matches = len(self.matches)
        self.total_points = sum(m.points_scored for m in self.matches) if self.matches else 0
        self.avg_points = round(self.total_points / self.total_matches, 2) if self.total_matches > 0 else 0
        
        
        # 1. Autónomo
        self.auto_count = sum(1 for m in self.matches if m.auto_moved) # Conteo (ej: 5)
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

        # --- 1. DATOS ---
        match_nums = [m.match_number for m in self.matches]
        points = [m.points_scored for m in self.matches]
        
        score_x = [m.score_x for m in self.matches if m.score_x is not None]
        score_y = [m.score_y for m in self.matches if m.score_y is not None]
        fail_x = [m.fail_x for m in self.matches if m.fail_x is not None]
        fail_y = [m.fail_y for m in self.matches if m.fail_y is not None]

        def fig_to_base64(fig):
            img = io.BytesIO()
            fig.savefig(img, format='png', bbox_inches='tight', transparent=True)
            img.seek(0)
            plt.close(fig)
            return base64.b64encode(img.getvalue()).decode()

        fig1, ax1 = plt.subplots(figsize=(12, 7))
        
        # --- GRÁFICA A: MAPA DE TIROS ---
        try:
            img_path = os.path.join(app.root_path, 'static', 'FRC2025.png')
            if os.path.exists(img_path):
                img = mpimg.imread(img_path)
                ax1.imshow(img, extent=[0, 100, 100, 0])
        except Exception as e:
            print(f"Error imagen: {e}")

        ax1.scatter(score_x, score_y, c='#28a745', label='Anotación', alpha=0.7, s=120, edgecolors='white')

        ax1.scatter(fail_x, fail_y, c='#dc3545', marker='x', label='Fallo', alpha=0.9, s=120, linewidths=3)

        ax1.set_title(f"Mapa de Tiros - {self.team_name}", fontsize=18)
        ax1.set_xlim(0, 100)
        ax1.set_ylim(100, 0)
        ax1.legend(loc='upper right', fontsize=12)
        ax1.axis('off')
        
        img_map = fig_to_base64(fig1)

        fig3, ax3 = plt.subplots(figsize=(6, 4))
        ax3.plot(match_nums, points, marker='o', linestyle='-', color='#004d99', linewidth=2)
        ax3.set_title('Progreso de Puntos')
        ax3.set_xlabel('Match')
        ax3.grid(True, linestyle='--', alpha=0.6)
        img_trend = fig_to_base64(fig3)

        # --- GRÁFICA B: ENDGAME (PASTEL) ---
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
    # --- FIN GRÁFICAS ---
    
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
        
        Dime: 1. Sus fortalezas. 2. Sus debilidades. 3. ¿Sirve para alianza? (Breve). 4.Resumen de los comentarios de los scouters.
        Evita usar bolds o viñetas, etc. solo texto plano. Si usas listas solo en numero no en viñetas
        """
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(contexto)
            return response.text
        except Exception as e:
            return f"Error IA: {str(e)}"


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
            drivetrain = request.form.get('drivetrain')
            print(f"Guardando PIT para {team_name}: {drivetrain}")

        elif form_type == 'match':
            
            try:
                match_num = int(request.form.get('match_number', 0))
                points = int(request.form.get('points', 0))
            except ValueError:
                match_num = 0
                points = 0

            auto_moved = True if request.form.get('auto_moved') else False
            has_failed = True if request.form.get('has_failed') else False
            played_defense = True if request.form.get('played_defense') else False
            
            try:
                s_x = int(request.form.get('score_x') or 0)
                s_y = int(request.form.get('score_y') or 0)
                f_x = int(request.form.get('fail_x') or 0)
                f_y = int(request.form.get('fail_y') or 0)
            except ValueError:
                s_x, s_y, f_x, f_y = 0, 0, 0, 0

            nuevo_match = MatchData(
                team_number = team_name,
                match_number = match_num,
                points_scored = points,
                has_failed = has_failed,
                auto_moved = auto_moved,
                endgame_result = request.form.get('endgame_result'),
                played_defense = played_defense,
                comments = request.form.get('comments'),
                
                # Aquí están las coordenadas nuevas:
                score_x = s_x,
                score_y = s_y,
                fail_x = f_x,
                fail_y = f_y
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
if __name__ == '__main__':
    app.run(debug=True)