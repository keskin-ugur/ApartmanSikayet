from flask import Flask, render_template, request, redirect, url_for, session, g, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'cok_gizli_anahtar' 

import os

# Dosyanın şu an bulunduğu klasörü otomatik bulur
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Veritabanı yolunu tam adres (absolute path) olarak ayarlar
DATABASE = os.path.join(BASE_DIR, 'apartman.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- VERİTABANI BAŞLATMA ---
def init_db():
    with app.app_context():
        db = get_db()
        
        # Users tablosu (Aynı)
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                phone_number TEXT UNIQUE, 
                role TEXT DEFAULT 'user'
            )
        ''')

        # Complaints tablosuna 'status' ekledik!
        db.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                description TEXT,
                is_anonymous INTEGER,
                status TEXT DEFAULT 'İnceleniyor',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Admin Kullanıcısı (Aynı)
        admin = db.execute("SELECT * FROM users WHERE full_name = 'admin'").fetchone()
        if not admin:
            db.execute("INSERT INTO users (full_name, phone_number, role) VALUES (?, ?, ?)",
                       ('admin', '12345', 'admin'))
            db.commit()

# --- ROTALAR ---

@app.route('/', methods=['GET', 'POST'])
def login():
    init_db() 
    
    if request.method == 'POST':
        # Formdan gelen veriler
        fullname_input = request.form.get('fullname') 
        phone_input = request.form.get('phone') 
        
        if not fullname_input or not phone_input:
            flash("Lütfen tüm alanları doldurun.", "error")
            return redirect(url_for('login'))

        db = get_db()

        # TEK SORGULAMA MANTIĞI:
        # İsim ve Telefon (Şifre) eşleşiyor mu?
        user = db.execute('SELECT * FROM users WHERE full_name = ? AND phone_number = ?', 
                          (fullname_input, phone_input)).fetchone()
        
        if user:
            # Kullanıcı (veya Admin) bulundu!
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            # Böyle biri yoksa, bu belki de yeni bir KAYIT işlemidir?
            # Ancak "admin" ismini başkası almasın diye kontrol edelim.
            if fullname_input == 'admin':
                flash("Hatalı admin şifresi (telefon numarası)!", "error")
                return redirect(url_for('login'))
                
            # Yeni kullanıcı kaydı (Otomatik)
            try:
                db.execute('INSERT INTO users (full_name, phone_number, role) VALUES (?, ?, ?)', 
                           (fullname_input, phone_input, 'user'))
                db.commit()
                
                # Kayıt sonrası hemen giriş yap
                new_user = db.execute('SELECT * FROM users WHERE phone_number = ?', (phone_input,)).fetchone()
                session['user_id'] = new_user['id']
                session['user_name'] = new_user['full_name']
                session['role'] = 'user'
                return redirect(url_for('dashboard'))
                
            except sqlite3.IntegrityError:
                flash("Bu telefon numarası zaten başka bir isimle kayıtlı.", "error")
                return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/sikayetler')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    db = get_db()
    
    # SORGULARI GÜNCELLİYORUZ
    if session.get('role') == 'admin':
        # Admin için: Users tablosuyla birleştirerek isim ve telefonu da alıyoruz
        sorgu = """
        SELECT complaints.*, users.full_name, users.phone_number 
        FROM complaints 
        LEFT JOIN users ON complaints.user_id = users.id 
        ORDER BY complaints.created_at DESC
        """
        sikayetler = db.execute(sorgu).fetchall()
    else:
        # Normal kullanıcı için: Sadece kendi şikayetleri
        sorgu = """
        SELECT * FROM complaints 
        WHERE user_id = ? 
        ORDER BY created_at DESC
        """
        sikayetler = db.execute(sorgu, (session['user_id'],)).fetchall()
        
    return render_template('dashboard.html', sikayetler=sikayetler, role=session['role'])

# ŞİFRE DEĞİŞTİRME (Aslında Telefon Numarası Güncelleme)
@app.route('/sifre-degistir', methods=['POST'])
def change_password():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    old_pass = request.form['old_password'] # Eski telefon no
    new_pass = request.form['new_password'] # Yeni telefon no
    
    db = get_db()
    
    # Admin'in telefon numarasını (şifresini) güncelle
    # Burada user_id'si oturumdan gelen kişinin phone_number'ını değiştiriyoruz
    user = db.execute('SELECT * FROM users WHERE id = ? AND phone_number = ?', (session['user_id'], old_pass)).fetchone()
    
    if user:
        try:
            db.execute('UPDATE users SET phone_number = ? WHERE id = ?', (new_pass, session['user_id']))
            db.commit()
            flash("Admin şifresi (telefon no) güncellendi!", "success")
        except:
             flash("Bir hata oluştu.", "error")
    else:
        flash("Eski şifre (telefon no) hatalı!", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/sikayet-ekle', methods=['POST'])
def add_complaint():
    # ... (Burası aynı kalıyor) ...
    if 'user_id' not in session: return redirect(url_for('login'))
    title = request.form['title']
    description = request.form['description']
    is_anonymous = 1 if request.form.get('is_anonymous') else 0
    db = get_db()
    db.execute('INSERT INTO complaints (user_id, title, description, is_anonymous) VALUES (?, ?, ?, ?)',
               (session['user_id'], title, description, is_anonymous))
    db.commit()
    return redirect(url_for('dashboard'))

@app.route('/cikis')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/cozuldu-isaretle/<int:id>', methods=['POST'])
def mark_resolved(id):
    # Güvenlik Kontrolü: Sadece Admin yapabilir
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute("UPDATE complaints SET status = 'Çözüldü' WHERE id = ?", (id,))
    db.commit()
    
    flash("Şikayet 'Çözüldü' olarak işaretlendi.", "success")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
