from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from markupsafe import Markup
import re

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# =========================
# МОДЕЛИ
# =========================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class Subsection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)


class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=True)
    formula = db.Column(db.Text, nullable=True)
    wolfram_code = db.Column(db.Text, nullable=True)
    literature = db.Column(db.Text, nullable=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey('subsection.id'), nullable=False)


# =========================
# LOGIN
# =========================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =========================
# ВНУТРЕННИЕ ССЫЛКИ
# Формат: [[Название материала]]
# =========================

def convert_internal_links(text):
    if not text:
        return ""

    pattern = r"\[\[(.*?)\]\]"

    def replace_link(match):
        material_title = match.group(1).strip()
        material = Material.query.filter_by(title=material_title).first()
        if material:
            link = url_for('material_detail', material_id=material.id)
            return f'<a href="{link}">{material_title}</a>'
        return material_title

    return Markup(re.sub(pattern, replace_link, text))


@app.template_filter('internal_links')
def internal_links_filter(text):
    return convert_internal_links(text)


# =========================
# ПУБЛИЧНЫЕ СТРАНИЦЫ
# =========================

@app.route('/')
def index():
    sections = Section.query.order_by(Section.title.asc()).all()
    return render_template('index.html', sections=sections)


@app.route('/section/<int:section_id>')
def section_detail(section_id):
    section = Section.query.get_or_404(section_id)
    subsections = Subsection.query.filter_by(section_id=section_id).order_by(Subsection.title.asc()).all()
    return render_template('section_detail.html', section=section, subsections=subsections)


@app.route('/subsection/<int:subsection_id>')
def subsection_detail(subsection_id):
    subsection = Subsection.query.get_or_404(subsection_id)
    materials = Material.query.filter_by(subsection_id=subsection_id).order_by(Material.title.asc()).all()
    section = Section.query.get(subsection.section_id)
    return render_template(
        'subsection_detail.html',
        subsection=subsection,
        section=section,
        materials=materials
    )


@app.route('/material/<int:material_id>')
def material_detail(material_id):
    material = Material.query.get_or_404(material_id)
    subsection = Subsection.query.get(material.subsection_id)
    section = Section.query.get(subsection.section_id)
    return render_template(
        'material_detail.html',
        material=material,
        subsection=subsection,
        section=section
    )


# =========================
# АВТОРИЗАЦИЯ
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            return redirect(url_for('admin'))

        return 'Неверный логин или пароль'

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# =========================
# АДМИНКА
# =========================

@app.route('/admin')
@login_required
def admin():
    sections = Section.query.order_by(Section.title.asc()).all()
    subsections = Subsection.query.order_by(Subsection.title.asc()).all()
    materials = Material.query.order_by(Material.title.asc()).all()

    return render_template(
        'admin.html',
        sections=sections,
        subsections=subsections,
        materials=materials
    )


# ---------- Разделы ----------

@app.route('/add_section', methods=['POST'])
@login_required
def add_section():
    title = request.form['title']
    description = request.form['description']

    new_section = Section(title=title, description=description)
    db.session.add(new_section)
    db.session.commit()

    return redirect(url_for('admin'))


@app.route('/edit_section/<int:section_id>', methods=['GET', 'POST'])
@login_required
def edit_section(section_id):
    section = Section.query.get_or_404(section_id)

    if request.method == 'POST':
        section.title = request.form['title']
        section.description = request.form['description']
        db.session.commit()
        return redirect(url_for('admin'))

    return render_template('edit_section.html', section=section)


@app.route('/delete_section/<int:section_id>', methods=['POST'])
@login_required
def delete_section(section_id):
    section = Section.query.get_or_404(section_id)

    subsections = Subsection.query.filter_by(section_id=section_id).all()
    for subsection in subsections:
        Material.query.filter_by(subsection_id=subsection.id).delete()
        db.session.delete(subsection)

    db.session.delete(section)
    db.session.commit()

    return redirect(url_for('admin'))


# ---------- Подразделы ----------

@app.route('/add_subsection', methods=['POST'])
@login_required
def add_subsection():
    title = request.form['title']
    description = request.form['description']
    section_id = request.form['section_id']

    new_subsection = Subsection(
        title=title,
        description=description,
        section_id=section_id
    )
    db.session.add(new_subsection)
    db.session.commit()

    return redirect(url_for('admin'))


@app.route('/edit_subsection/<int:subsection_id>', methods=['GET', 'POST'])
@login_required
def edit_subsection(subsection_id):
    subsection = Subsection.query.get_or_404(subsection_id)
    sections = Section.query.order_by(Section.title.asc()).all()

    if request.method == 'POST':
        subsection.title = request.form['title']
        subsection.description = request.form['description']
        subsection.section_id = request.form['section_id']
        db.session.commit()
        return redirect(url_for('admin'))

    return render_template('edit_subsection.html', subsection=subsection, sections=sections)


@app.route('/delete_subsection/<int:subsection_id>', methods=['POST'])
@login_required
def delete_subsection(subsection_id):
    subsection = Subsection.query.get_or_404(subsection_id)

    Material.query.filter_by(subsection_id=subsection_id).delete()
    db.session.delete(subsection)
    db.session.commit()

    return redirect(url_for('admin'))


# ---------- Материалы ----------

@app.route('/add_material', methods=['POST'])
@login_required
def add_material():
    title = request.form['title']
    description = request.form['description']
    formula = request.form['formula']
    wolfram_code = request.form['wolfram_code']
    literature = request.form['literature']
    subsection_id = request.form['subsection_id']

    new_material = Material(
        title=title,
        description=description,
        formula=formula,
        wolfram_code=wolfram_code,
        literature=literature,
        subsection_id=subsection_id
    )
    db.session.add(new_material)
    db.session.commit()

    return redirect(url_for('admin'))


@app.route('/edit_material/<int:material_id>', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    material = Material.query.get_or_404(material_id)
    subsections = Subsection.query.order_by(Subsection.title.asc()).all()

    if request.method == 'POST':
        material.title = request.form['title']
        material.description = request.form['description']
        material.formula = request.form['formula']
        material.wolfram_code = request.form['wolfram_code']
        material.literature = request.form['literature']
        material.subsection_id = request.form['subsection_id']
        db.session.commit()
        return redirect(url_for('material_detail', material_id=material.id))

    return render_template('edit_material.html', material=material, subsections=subsections)


@app.route('/delete_material/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    material = Material.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()
    return redirect(url_for('admin'))


# =========================
# ЗАПУСК
# =========================
with app.app_context():
    db.create_all()

    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='1234')
        db.session.add(admin)
        db.session.commit()
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        

    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
