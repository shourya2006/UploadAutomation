import os
import json
import threading
import queue
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from social_uploader import publish_all

load_dotenv()

app = Flask(__name__)
# Change UPLOAD_FOLDER to static so frontend can access the thumbnail
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/publish', methods=['POST'])
def publish():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
        
    file = request.files['video']
    prompt = request.form.get('prompt')
    
    if file.filename == '':
        return jsonify({"error": "No video selected"}), 400
        
    if not prompt:
        return jsonify({"error": "Prompt/Description is required"}), 400
        
    filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(video_path)
    
    thumb_path = None
    if 'thumbnail' in request.files:
        thumb_file = request.files['thumbnail']
        if thumb_file.filename != '':
            thumb_filename = secure_filename(thumb_file.filename)
            # Prepend video filename to make it unique per upload
            thumb_filename = filename.rsplit('.', 1)[0] + "_" + thumb_filename
            thumb_path = os.path.join(app.config['UPLOAD_FOLDER'], thumb_filename)
            thumb_file.save(thumb_path)
    
    # We use a queue to pass streaming messages from the background thread to the response generator
    q = queue.Queue()
    
    def progress_callback(update_dict):
        q.put(update_dict)

    def run_publish():
        try:
            yt_url = publish_all(video_path, prompt, thumbnail_path=thumb_path, progress_callback=progress_callback)
            q.put({"type": "complete", "youtube_url": yt_url})
        except Exception as e:
            import traceback
            traceback.print_exc()
            q.put({"type": "error", "message": str(e)})

    threading.Thread(target=run_publish).start()
    
    def generate_stream():
        while True:
            item = q.get()
            # Send as SSE format
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("type") in ["complete", "error"]:
                break
                
    return Response(generate_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
