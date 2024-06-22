from datetime import datetime
import os
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from werkzeug.utils import secure_filename
import octk
from . import scrape_pdf
import pandas as pd
from pathlib import Path

UPLOAD_FOLDER = r'data/uploads'
OUTPUT_FOLDER = r'data/output'
ALLOWED_EXTENSIONS = {'pdf'}


def ensure_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, UPLOAD_FOLDER)
    app.config['OUTPUT_FOLDER'] = os.path.join(app.instance_path, OUTPUT_FOLDER)

    ensure_dir_exists(app.config['UPLOAD_FOLDER'])
    ensure_dir_exists(app.config['OUTPUT_FOLDER'])

    app.add_url_rule(
        "/uploads/<name>", endpoint="download_file", build_only=True
    )

    def process_upload(file):
        upload_file_name = "upload_" + datetime.now().strftime("%Y-%m-%d_%H%M") + ".pdf"
        full_save_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_file_name)
        full_save_path = octk.uniquify(full_save_path)
        file.save(full_save_path)

        units_list: list[scrape_pdf.Unit] = scrape_pdf.extract_page_data(file)
        df = pd.DataFrame(units_list, columns=scrape_pdf.Unit._fields)

        outfile_name = upload_file_name.replace(".pdf", ".csv")
        data_file_path = Path(app.config['OUTPUT_FOLDER'], outfile_name)
        df.to_csv(data_file_path, index=False)
        return data_file_path

    @app.route('/', methods=['GET', 'POST'])
    def upload_file():
        if request.method == 'POST':
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                file.filename = secure_filename(file.filename)
                output_file_path = process_upload(file)
                return redirect(url_for('success', file_name=output_file_path.name))
        # url_for('download_file', name=output_file_path.name)
        return render_template('index.html')

    @app.route('/extraction_complete/<file_name>')
    def success(file_name):
        return render_template('success.html', file_name=file_name)

    @app.route('/uploads/<file_name>')
    def download_file(file_name):
        return send_from_directory(app.config['OUTPUT_FOLDER'], file_name, as_attachment=True)

    return app


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


if __name__ == '__main__':
    create_app().run(debug=True, port=5012)
