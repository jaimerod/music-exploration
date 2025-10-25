import os
from dotenv import load_dotenv  # <-- NEW: Import the library

import googleapiclient.discovery
import googleapiclient.errors
from operator import itemgetter

load_dotenv()

API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not API_KEY:
    # Updated the error message to be more helpful
    raise ValueError("YOUTUBE_API_KEY not set. Check your .env file.")

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
youtube = googleapiclient.discovery.build(
    API_SERVICE_NAME, API_VERSION, developerKey=API_KEY
)

def get_top_100_songs(search_query: str):
    """
    Finds the top 100 songs for a search query, sorted by view count.
    """
    video_ids = []
    next_page_token = None

    print(f"Searching for videos related to: '{search_query}'...")

    try:
        while len(video_ids) < 100:
            results_to_fetch = min(50, 100 - len(video_ids))

            search_request = youtube.search().list(
                part="id",
                q=search_query,
                maxResults=results_to_fetch,
                type="video",
                order="viewCount",
                videoCategoryId="10",
                pageToken=next_page_token
            )
            search_response = search_request.execute()

            for item in search_response['items']:
                video_ids.append(item['id']['videoId'])

            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break

        if not video_ids:
            print("No video results found.")
            return []

        print(f"Found {len(video_ids)} video IDs. Fetching details...")

        video_details = []
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i : i + 50]
            ids_string = ",".join(batch_ids)

            video_request = youtube.videos().list(
                part="snippet,statistics",
                id=ids_string
            )
            video_response = video_request.execute()
            video_details.extend(video_response['items'])

        print("Details fetched. Sorting results...")

        valid_videos = [
            v for v in video_details if 'statistics' in v and 'viewCount' in v['statistics']
        ]

        sorted_videos = sorted(
            valid_videos,
            key=lambda item: int(item['statistics']['viewCount']),
            reverse=True
        )

        return sorted_videos

    except googleapiclient.errors.HttpError as e:
        print(f"\nAn API error occurred: {e}")
        return None

if __name__ == "__main__":

    QUERY = input("What do you want to Search for?  ")

    top_100 = get_top_100_songs(QUERY)

    if top_100:
        print(f"\n--- Top {len(top_100)} Songs for '{QUERY}' (Sorted by Views) ---")

        for i, video in enumerate(top_100):
            title = video['snippet']['title']
            views = int(video['statistics']['viewCount'])
            video_id = video['id']
            url = f"https://music.youtube.com/watch?v={video_id}"

            print(f"{i + 1:3}. {title}\n     Views: {views:,.0f} | URL: {url}\n")