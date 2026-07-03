import os
import csv
import io
import sqlite3
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, Response, g, current_app
)

contacts_bp = Blueprint('contacts', __name__, template_folder='templates', static_folder='static')

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), 'contacts.db'))

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

SMTP_HOST     = os.environ.get('SMTP_HOST', '')
SMTP_PORT     = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER     = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM     = os.environ.get('SMTP_FROM', SMTP_USER)
SMTP_USE_SSL  = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'

ANREDEN = ['Herr', 'Frau', 'Divers', 'Firma']

# Baureihen fuer das Auswahlfeld + kurze Kundeninfo fuer die Dankes-Mail.
BAUREIHEN = [
    {'code': 'CS',  'label': 'CS Serie (21-26 PS) - Garten & kleine Flaechen',
     'info': 'Die CS Serie ist unser wendiger Kompakttraktor fuer Garten, Reitplatz und kleine Flaechen - kraftvoll und einfach zu bedienen.'},
    {'code': 'CX',  'label': 'CX Serie (25 PS) - Hof & Reitstall',
     'info': 'Die CX Serie eignet sich ideal fuer Hof, Reitstall und Gewaechshaus - kompakt, wendig und vielseitig einsetzbar.'},
    {'code': 'CK',  'label': 'CK Serie (25-50 PS) - vielseitig',
     'info': 'Die CK Serie ist unser Allrounder fuer Kommune und mittlere Betriebe - stark, zuverlaessig und vielseitig.'},
    {'code': 'DK',  'label': 'DK Serie (bis 60 PS) - kraftvoll',
     'info': 'Die DK Serie ueberzeugt mit Kraft fuer Kommune und Golfplatz - leistungsstark und komfortabel.'},
    {'code': 'RX',  'label': 'RX Serie (66-74 PS) - Profi-Landwirtschaft',
     'info': 'Die RX Serie ist fuer die professionelle Landwirtschaft gemacht - kraftvoll, effizient, ausdauernd.'},
    {'code': 'HX',  'label': 'HX Serie (91-140 PS) - Profi & autonome Technik',
     'info': 'Die HX Serie ist unser Flaggschiff fuer die professionelle Landwirtschaft, inklusive modernster, teils autonomer Technik.'},
    {'code': 'K9',  'label': 'K9 (24 PS) - kompakt & vielseitig',
     'info': 'Der K9 ist kompakt, vielseitig und ideal fuer Hobby- und Kommunaleinsatz.'},
    {'code': 'ZXR', 'label': 'ZXR - Rasenpflege',
     'info': 'Die ZXR Nullwendekreismaeher sorgen fuer perfekte Rasenpflege mit maximaler Wendigkeit.'},
    {'code': 'ZXS', 'label': 'ZXS - Rasenpflege',
     'info': 'Die ZXS Nullwendekreismaeher sorgen fuer perfekte Rasenpflege mit maximaler Wendigkeit.'},
    {'code': 'SONSTIGES', 'label': 'Sonstiges / noch unklar',
     'info': 'Gerne beraten wir dich persoenlich, welches KIOTI-Modell am besten zu deinem Einsatz passt.'},
]
BAUREIHEN_BY_CODE = {b['code']: b for b in BAUREIHEN}


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@contacts_bp.teardown_app_request
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = sqlite3.connect(DB_PATH)
        db.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                anrede TEXT,
                vorname TEXT,
                nachname TEXT,
                strasse TEXT,
                hausnummer TEXT,
                plz TEXT,
                ort TEXT,
                land TEXT,
                email TEXT,
                baureihe TEXT,
                notizen TEXT,
                einwilligung INTEGER NOT NULL DEFAULT 0,
                email_status TEXT NOT NULL DEFAULT 'ausstehend'
            )
        """)
        db.commit()
        db.close()


def send_thank_you_email(contact):
    """Schickt die automatische Dankes-Mail nach Messebesuch. Gibt (ok, fehlermeldung) zurueck."""
    if not contact['email']:
        return False, 'keine E-Mail-Adresse angegeben'
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        return False, 'SMTP ist nicht konfiguriert'

    baureihe = BAUREIHEN_BY_CODE.get(contact['baureihe'], BAUREIHEN_BY_CODE['SONSTIGES'])
    anrede_zeile = {
        'Herr': f"Hallo Herr {contact['nachname']},",
        'Frau': f"Hallo Frau {contact['nachname']},",
    }.get(contact['anrede'], f"Hallo {contact['vorname']},")

    body = (
        f"{anrede_zeile}\n\n"
        f"vielen Dank fuer deinen Besuch an unserem Messestand! Es hat uns gefreut,\n"
        f"dich kennenzulernen und mit dir ueber KIOTI-Traktoren zu sprechen.\n\n"
        f"Zu deinem Interesse an der {baureihe['label']}:\n"
        f"{baureihe['info']}\n\n"
        f"Wir melden uns in Kuerze persoenlich bei dir mit weiteren Informationen.\n"
        f"Bei Fragen kannst du jederzeit auf diese E-Mail antworten.\n\n"
        f"Viele Gruesse\nDein KIOTI-Team"
    )

    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = 'Danke fuer deinen Besuch bei KIOTI'
    msg['From'] = SMTP_FROM
    msg['To'] = contact['email']

    try:
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [contact['email']], msg.as_string())
        server.quit()
        return True, ''
    except Exception as exc:
        return False, str(exc)


def require_admin_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not ADMIN_PASSWORD:
            return Response(
                'Admin-Bereich ist nicht konfiguriert. Bitte ADMIN_PASSWORD setzen.',
                status=503,
            )
        auth = request.authorization
        if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
            return Response(
                'Anmeldung erforderlich', status=401,
                headers={'WWW-Authenticate': 'Basic realm="Kioti Kontakte"'},
            )
        return view(*args, **kwargs)
    return wrapped


@contacts_bp.route('/kontakt', methods=['GET'])
def kontakt_form():
    return render_template('kontakt_form.html', anreden=ANREDEN, baureihen=BAUREIHEN)


@contacts_bp.route('/kontakt', methods=['POST'])
def kontakt_submit():
    f = request.form
    errors = []
    required = {
        'vorname': 'Vorname', 'nachname': 'Nachname', 'email': 'E-Mail', 'baureihe': 'Baureihe',
    }
    for field, label in required.items():
        if not f.get(field, '').strip():
            errors.append(f'{label} ist ein Pflichtfeld.')
    if not f.get('einwilligung'):
        errors.append('Bitte der Speicherung der Daten zustimmen.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return render_template(
            'kontakt_form.html', anreden=ANREDEN, baureihen=BAUREIHEN, form=f,
        ), 400

    contact = {
        'created_at': datetime.utcnow().isoformat(timespec='seconds'),
        'anrede': f.get('anrede', '').strip(),
        'vorname': f.get('vorname', '').strip(),
        'nachname': f.get('nachname', '').strip(),
        'strasse': f.get('strasse', '').strip(),
        'hausnummer': f.get('hausnummer', '').strip(),
        'plz': f.get('plz', '').strip(),
        'ort': f.get('ort', '').strip(),
        'land': f.get('land', '').strip() or 'Deutschland',
        'email': f.get('email', '').strip(),
        'baureihe': f.get('baureihe', '').strip(),
        'notizen': f.get('notizen', '').strip(),
        'einwilligung': 1,
    }

    db = get_db()
    cur = db.execute(
        """INSERT INTO contacts
           (created_at, anrede, vorname, nachname, strasse, hausnummer, plz, ort, land,
            email, baureihe, notizen, einwilligung, email_status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (contact['created_at'], contact['anrede'], contact['vorname'], contact['nachname'],
         contact['strasse'], contact['hausnummer'], contact['plz'], contact['ort'], contact['land'],
         contact['email'], contact['baureihe'], contact['notizen'], contact['einwilligung'], 'ausstehend'),
    )
    db.commit()
    contact_id = cur.lastrowid

    ok, err = send_thank_you_email(contact)
    status = 'gesendet' if ok else f'fehler: {err}'
    db.execute('UPDATE contacts SET email_status = ? WHERE id = ?', (status, contact_id))
    db.commit()

    return redirect(url_for('contacts.kontakt_success', vorname=contact['vorname']))


@contacts_bp.route('/kontakt/danke')
def kontakt_success():
    return render_template('kontakt_success.html', vorname=request.args.get('vorname', ''))


@contacts_bp.route('/kontakte')
@require_admin_auth
def kontakte_list():
    suche = request.args.get('q', '').strip()
    db = get_db()
    if suche:
        like = f'%{suche}%'
        rows = db.execute(
            """SELECT * FROM contacts
               WHERE nachname LIKE ? OR vorname LIKE ? OR ort LIKE ? OR baureihe LIKE ?
               ORDER BY created_at DESC""",
            (like, like, like, like),
        ).fetchall()
    else:
        rows = db.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
    return render_template('kontakte_list.html', rows=rows, suche=suche, baureihen_by_code=BAUREIHEN_BY_CODE)


@contacts_bp.route('/kontakte/export.csv')
@require_admin_auth
def kontakte_export():
    db = get_db()
    rows = db.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow([
        'ID', 'Erfasst am', 'Anrede', 'Vorname', 'Nachname', 'Strasse', 'Hausnummer',
        'PLZ', 'Ort', 'Land', 'E-Mail', 'Baureihe', 'Notizen', 'E-Mail-Status',
    ])
    for r in rows:
        writer.writerow([
            r['id'], r['created_at'], r['anrede'], r['vorname'], r['nachname'],
            r['strasse'], r['hausnummer'], r['plz'], r['ort'], r['land'], r['email'],
            r['baureihe'], r['notizen'], r['email_status'],
        ])
    return Response(
        out.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=kioti_kontakte.csv'},
    )
