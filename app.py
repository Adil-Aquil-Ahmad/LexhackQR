from flask import Flask, render_template, Response, jsonify
import cv2
from pyzbar.pyzbar import decode
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# Load attendee IDs
attendees_df = pd.read_csv('attendees.csv')
attendee_ids = set(attendees_df['id'].astype(str))

# Global variables to store the scanned ID and its status
scanned_id = None
scanned_status = None
last_scanned_id = None  # To track the last scanned ID

# Function to mark attendance in a specific CSV file
def mark_attendance(scanned_id, file_name):
    try:
        # Try to read the CSV file
        attendance_df = pd.read_csv(file_name)
        # If the file is empty, initialize it with the required columns
        if attendance_df.empty:
            attendance_df = pd.DataFrame(columns=['id', 'timestamp'])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        # If the file doesn't exist or is empty, create a new DataFrame
        attendance_df = pd.DataFrame(columns=['id', 'timestamp'])

    # Check if the scanned ID is already in the attendance file
    if scanned_id not in attendance_df['id'].values:
        # If not, add the ID with the current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_record = pd.DataFrame([[scanned_id, timestamp]], columns=['id', 'timestamp'])
        attendance_df = pd.concat([attendance_df, new_record], ignore_index=True)
        attendance_df.to_csv(file_name, index=False)
        return "success"
    else:
        return "duplicate"

def generate_frames(file_name):
    global scanned_id, scanned_status, last_scanned_id
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            qr_detected = False
            for barcode in decode(frame):
                qr_detected = True
                scanned_id = barcode.data.decode('utf-8')
                if scanned_id == last_scanned_id:
                    # Skip processing if the same QR code is detected again
                    scanned_status = "duplicate"
                    continue

                if scanned_id in attendee_ids:
                    # Check if the ID has already been scanned
                    scanned_status = mark_attendance(scanned_id, file_name)
                    if scanned_status == "success":
                        last_scanned_id = scanned_id  # Update the last scanned ID
                else:
                    scanned_status = "invalid"

            if not qr_detected:
                scanned_id = None
                scanned_status = None

            # Encode the frame and yield it
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed/<category>')
def video_feed(category):
    file_name = f'attendance_{category}.csv'
    return Response(generate_frames(file_name),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_scanned_id')
def get_scanned_id():
    global scanned_id, scanned_status
    return jsonify({"scanned_id": scanned_id, "status": scanned_status})

if __name__ == '__main__':
    app.run(debug=True)