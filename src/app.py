import os
import requests
from dotenv import load_dotenv
# --- NEW IMPORT ---
from flask import Flask, render_template, request, flash, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import googleapiclient.discovery
import googleapiclient.errors

# --- CONFIGURATION (No changes here) ---

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
API_KEY = os.environ.get("YOUTUBE_API_KEY")
app.config['RECAPTCHA_SITE_KEY'] = os.environ.get('RECAPTCHA_SITE_KEY')
app.config['RECAPTCHA_SECRET_KEY'] = os.environ.get('RECAPTCHA_SECRET_KEY')

if not all([API_KEY, app.config['SECRET_KEY'], app.config['RECAPTCHA_SITE_KEY'], app.config['RECAPTCHA_SECRET_KEY']]):
    raise ValueError("One or more required environment variables are not set. Check your .env file.")

youtube = googleapiclient.discovery.build(
    "youtube", "v3", developerKey=API_KEY
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# --- YOUTUBE SEARCH LOGIC (No changes here) ---

def search_youtube_music(query: str, max_results: int = 100):
    # (This function is identical to your current one)
    video_ids = []
    next_page_token = None
    try:
        while len(video_ids) < max_results:
            results_to_fetch = min(50, max_results - len(video_ids))
            search_request = youtube.search().list(
                part="id", q=query, maxResults=results_to_fetch, type="video",
                order="viewCount", videoCategoryId="10", pageToken=next_page_token
            )
            search_response = search_request.execute()
            for item in search_response['items']:
                video_ids.append(item['id']['videoId'])
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break
        if not video_ids: return []

        video_details = []
        for i in range(0, len(video_ids), 50):
            ids_string = ",".join(video_ids[i : i + 50])
            video_request = youtube.videos().list(
                part="snippet,statistics", id=ids_string
            )
            video_response = video_request.execute()
            video_details.extend(video_response['items'])

        formatted_results = []
        for item in video_details:
            if 'statistics' not in item or 'viewCount' not in item['statistics']:
                continue
            views = int(item['statistics']['viewCount'])
            video_id = item['id']
            formatted_results.append({
                "id": video_id,
                "title": item['snippet']['title'],
                "thumbnail_url": item['snippet']['thumbnails']['medium']['url'],
                "views_formatted": f"{views:,.0f}",
                "url": f"https://music.youtube.com/watch?v={video_id}"
            })
        formatted_results.sort(key=lambda v: int(v['views_formatted'].replace(',', '')), reverse=True)
        return formatted_results
    except googleapiclient.errors.HttpError as e:
        print(f"\nAn API error occurred: {e}")
        return None

# --- WEBSITE ROUTES (MODIFIED) ---

@app.route('/', methods=['GET'])
def index():
    """
    Main page - now ONLY handles GET requests.
    It just renders the empty page.
    """
    return render_template('index.html',
                           recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'])


@app.route('/search', methods=['POST'])
@limiter.limit("1 per 5 second", methods=['POST'])
def search():
    """
    NEW search route. This handles the JavaScript fetch request.
    It's protected by the limiter and reCAPTCHA.
    """
    data = request.json
    query = data.get('query')
    recaptcha_response = data.get('g-recaptcha-response')

    # 1. Verify reCAPTCHA
    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    payload = {
        'secret': app.config['RECAPTCHA_SECRET_KEY'],
        'response': recaptcha_response
    }
    verify_request = requests.post(verify_url, data=payload)
    verify_json = verify_request.json()

    if not verify_json.get('success'):
        # Return a JSON error
        return jsonify({"error": "reCAPTCHA verification failed."}), 400

    # 2. Perform search if reCAPTCHA is valid
    if query:
        results = search_youtube_music(query)
        if results is None:
            return jsonify({"error": "Error fetching data from YouTube."}), 500

        # Return the results as JSON
        return jsonify(results)

    return jsonify({"error": "No query provided."}), 400

# --- RUN THE APP ---
if __name__ == "__main__":
    app.run(debug=True)