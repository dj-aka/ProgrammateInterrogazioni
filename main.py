from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
import random, string, io
from fpdf import FPDF
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret-key"
app.permanent_session_lifetime = timedelta(minutes=5)

# Struttura per memorizzare le stanze:
# rooms[room_code] = {
#    "creator": "CREATOR",
#    "dates": [ {"date": <string>, "capacity": <int>} ],
#    "participants": [ { "name": <string>, "preferences": [<date strings>] } ],
#    "schedule": { <date>: [<participant name>, ...] }
# }
rooms = {}

def generate_room_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.template_filter('day_of_week')
def day_of_week(date_str):
    mapping = {
        'Monday': 'LUNEDÌ',
        'Tuesday': 'MARTEDÌ',
        'Wednesday': 'MERCOLEDÌ',
        'Thursday': 'GIOVEDÌ',
        'Friday': 'VENERDÌ',
        'Saturday': 'SABATO',
        'Sunday': 'DOMENICA'
    }
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return mapping.get(dt.strftime('%A'), dt.strftime('%A'))
    except Exception:
        return date_str

@app.template_filter('format_date_pref')
def format_date_pref(date_str):
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        day_mapping = {
            'Monday': 'LUNEDÌ',
            'Tuesday': 'MARTEDÌ',
            'Wednesday': 'MERCOLEDÌ',
            'Thursday': 'GIOVEDÌ',
            'Friday': 'VENERDÌ',
            'Saturday': 'SABATO',
            'Sunday': 'DOMENICA'
        }
        month_mapping = {
            'January': 'gennaio',
            'February': 'febbraio',
            'March': 'marzo',
            'April': 'aprile',
            'May': 'maggio',
            'June': 'giugno',
            'July': 'luglio',
            'August': 'agosto',
            'September': 'settembre',
            'October': 'ottobre',
            'November': 'novembre',
            'December': 'dicembre'
        }
        day_name = day_mapping.get(dt.strftime('%A'), dt.strftime('%A').upper())
        month_name = month_mapping.get(dt.strftime('%B'), dt.strftime('%B').lower())
        return f"{day_name} {dt.day} {month_name}"
    except Exception:
        return date_str

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/create', methods=["GET", "POST"])
def create_room():
    if request.method == "POST":
        dates_input = request.form.get("dates")
        if not dates_input:
            flash("Inserisci le date disponibili.")
            return redirect(url_for("create_room"))
        dates = []
        for line in dates_input.strip().splitlines():
            parts = line.split(',')
            if len(parts) != 2:
                continue
            date_str = parts[0].strip()
            try:
                capacity = int(parts[1].strip())
            except:
                capacity = 0
            if date_str and capacity > 0:
                dates.append({"date": date_str, "capacity": capacity})
        if not dates:
            flash("Inserisci almeno una data valida con capacità.")
            return redirect(url_for("create_room"))
        room_code = generate_room_code()
        rooms[room_code] = {
            "creator": "CREATOR",
            "dates": dates,
            "participants": [],
            "schedule": {}
        }
        session['role'] = 'creator'
        session.pop('name', None)
        session['room_code'] = room_code
        flash(f"Stanza creata! Codice: {room_code}")
        return redirect(url_for("room", room_code=room_code))
    return render_template("create_room.html")

@app.route('/join', methods=["GET", "POST"])
def join_room():
    # Precompila il codice stanza se passato nella query string (es: ?room_code=ABC123)
    room_code_prefill = request.args.get("room_code", "").upper()
    if request.method == "POST":
        room_code = request.form.get("room_code").upper()
        name = request.form.get("name")
        if room_code not in rooms:
            flash("Codice stanza non valido.")
            return redirect(url_for("join_room"))
        if not name:
            flash("Inserisci il tuo nome.")
            return redirect(url_for("join_room"))
        room = rooms[room_code]
        if name.strip().lower() == room["creator"].strip().lower():
            flash("Il creatore non può partecipare.")
            return redirect(url_for("join_room"))
        for p in room["participants"]:
            if p["name"].strip().lower() == name.strip().lower():
                flash("Nome già in uso.")
                return redirect(url_for("join_room"))
        room["participants"].append({"name": name, "preferences": []})
        session['name'] = name
        session['role'] = 'participant'
        session['room_code'] = room_code
        flash("Accesso effettuato!")
        return redirect(url_for("room_participant", room_code=room_code))
    return render_template("join_room.html", room_code_prefill=room_code_prefill)

@app.route('/room/<room_code>', methods=["GET", "POST"])
def room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]

    # Se l'utente non è il creatore, forziamo sempre il login tramite il form join:
    if session.get('role') != 'creator':
        session.pop('name', None)
        session.pop('room_code', None)
        return redirect(url_for("join_room", room_code=room_code))

    # Per il creatore, ignoriamo eventuali POST (non serve inviare preferenze)
    if request.method == "POST":
        flash("Solo i partecipanti possono inviare preferenze.")
        return redirect(url_for("room", room_code=room_code))

    return render_template("room_creator.html", room=room, room_code=room_code)

@app.route('/room_participant/<room_code>', methods=["GET", "POST"])
def room_participant(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]
    if request.method == "POST":
        if session.get('role') != 'participant':
            flash("Solo i partecipanti possono impostare le preferenze.")
            return redirect(url_for("room_participant", room_code=room_code))
        name = session.get('name')
        preferences = request.form.getlist("preference[]")
        for participant in room["participants"]:
            if participant["name"] == name:
                valid = [d["date"] for d in room["dates"]]
                participant["preferences"] = [pref for pref in preferences if pref in valid]
                flash("Preferenze salvate!")
                break
        return redirect(url_for("wait_room", room_code=room_code))
    return render_template("room_participant.html", room=room, room_code=room_code)

@app.route('/wait_room/<room_code>')
def wait_room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]
    return render_template("wait_room.html", room=room, room_code=room_code)

@app.route('/modify_preferences/<room_code>')
def modify_preferences(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]
    if session.get('role') == 'participant' and session.get('name'):
        for participant in room["participants"]:
            if participant["name"] == session.get('name'):
                participant["preferences"] = []  # Reset delle preferenze (rimuove il badge inviato)
                flash("Preferenze rimosse. Ora puoi modificarle.")
                break
    return redirect(url_for("room_participant", room_code=room_code))

@app.route('/schedule/<room_code>', methods=["POST", "GET"])
def schedule(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]
    if request.method == "POST" or not room["schedule"]:
        if session.get('role') == 'creator':
            room["schedule"] = {}
            date_capacities = {d["date"]: d["capacity"] for d in room["dates"]}
            assignments = {date: [] for date in date_capacities}
            remaining = date_capacities.copy()
            participants = room["participants"].copy()
            random.shuffle(participants)
            for participant in participants:
                if not participant["preferences"]:
                    continue
                for pref in participant["preferences"]:
                    if remaining.get(pref, 0) > 0:
                        assignments[pref].append(participant["name"])
                        remaining[pref] -= 1
                        break
            for participant in participants:
                if participant["name"] not in [name for names in assignments.values() for name in names]:
                    available = [date for date, cap in remaining.items() if cap > 0]
                    if available:
                        chosen = random.choice(available)
                        assignments[chosen].append(participant["name"])
                        remaining[chosen] -= 1
            room["schedule"] = assignments
            flash("Programmazione generata con successo!")
        else:
            flash("Solo il creatore può generare la programmazione.")
    return render_template("schedule.html", room=room, room_code=room_code)

@app.route('/downloadpdf/<room_code>')
def downloadpdf(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        flash("Stanza non trovata.")
        return redirect(url_for("index"))
    room = rooms[room_code]
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(0, 10, txt=f"Programmazione per la Stanza {room_code}", ln=1, align="C")
    pdf.ln(5)
    for date, participants in room.get("schedule", {}).items():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, txt=f"{date}", ln=1)
        pdf.set_font("Arial", size=12)
        if participants:
            for name in participants:
                pdf.cell(0, 10, txt=f"- {name}", ln=1)
        else:
            pdf.cell(0, 10, txt="Nessun partecipante assegnato", ln=1)
        pdf.ln(2)
    pdf_output = pdf.output(dest="S").encode("latin1")
    return send_file(io.BytesIO(pdf_output),
                     mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f"schedulazione_{room_code}.pdf")

@app.route('/participants/<room_code>')
def participants(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        return jsonify({"error": "Stanza non trovata"}), 404
    room = rooms[room_code]
    data = [{"name": p["name"], "submitted": bool(p["preferences"])} for p in room["participants"]]
    return jsonify({"participants": data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
