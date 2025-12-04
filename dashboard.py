
from flask import Flask, render_template, request
from ecoindex import get_encode_score
from analysis import run_analysis

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    
    website_url = request.form.get('website')

    if not website_url:
        return render_template('index.html', error="Veuillez saisir une URL.")
    try:
        report = run_analysis(website_url)

        summary = report.get("summary", {})

        score = get_encode_score(website_url)
        
        return render_template('index.html', summary=summary, score=score, website=website_url)
    except Exception as e:
        return render_template('index.html', error=f"Erreur: {e}")

if __name__ == '__main__': 
    app.run(debug=True)




