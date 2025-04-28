from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

# Sample data for targets and obstacles with image references
targets = [
    {"id": 1, "image": "target1.jpg", "x": 100, "y": 200, "z": 50},
    {"id": 2, "image": "target2.jpg", "x": 150, "y": 250, "z": 30},
    {"id": 3, "image": "target3.jpg", "x": 200, "y": 300, "z": 20},
    {"id": 4, "image": "target4.jpg", "x": 250, "y": 350, "z": 10},
]

obstacles = [
    {"id": 1, "image": "obstacle1.jpg", "x": 50, "y": 100, "z": 60},
    {"id": 2, "image": "obstacle2.jpg", "x": 75, "y": 150, "z": 40},
]

@app.route('/')
def index():
    return render_template('index.html', targets=targets, obstacles=obstacles)

# Route to serve static images
@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)

if __name__ == '__main__':
    app.run(debug=True)