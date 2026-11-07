# Flask = the tool that runs our web server
from flask import Flask

# Create the web server
app = Flask(__name__)


# Home page: just shows the server is on
@app.get("/")
def home():
    return "SoundSense is running"


# Start the server when we run "python app.py"
if __name__ == "__main__":
    app.run(port=5000)
    