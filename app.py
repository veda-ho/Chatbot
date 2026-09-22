#import flask (using backend/web framework)
from flask import Flask, render_template 

#creates web application
app = Flask(__name__)


#when someone visit homepage, show them HTML
@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)