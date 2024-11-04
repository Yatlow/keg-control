from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Initialize your variables here
variable1 = "1.5"

@app.route('/')
def index():
    return render_template('index.html', variable1=variable1)

@app.route('/update', methods=['POST'])
def update_variable():
    global variable1
    variable1 = request.form['variable1']
    # Add logic to update your machine with the new variable if necessary
    return jsonify(success=True, new_value=variable1)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
