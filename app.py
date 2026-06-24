from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os

from rag import process_pdf, query, is_ready

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():

    if "pdf" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file uploaded"
        }), 400

    file = request.files["pdf"]

    if file.filename == "":
        return jsonify({
            "status": "error",
            "message": "No file selected"
        }), 400

    filename = secure_filename(file.filename)

    pdf_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(pdf_path)

    try:
        stats = process_pdf(pdf_path)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to process PDF: {str(e)}"
        }), 500

    return jsonify({
        "status": "success",
        "message": "PDF processed successfully",
        "stats": stats
    })


@app.route("/chat", methods=["POST"])
def chat():

    if not is_ready():
        return jsonify({
            "status": "error",
            "message": "Upload a PDF first"
        }), 400

    data = request.get_json(force=True, silent=True)

    if not data or not data.get("question", "").strip():
        return jsonify({
            "status": "error",
            "answer": "Question cannot be empty."
        }), 400

    question = data["question"].strip()

    try:
        answer = query(question)
    except Exception as e:
        return jsonify({
            "status": "error",
            "answer": f"Error: {str(e)}"
        }), 500

    return jsonify({
        "status": "success",
        "answer": answer
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )