import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def auth_youtube():
    print("Initiating YouTube Authentication...")
    if not os.path.exists("client_secrets.json"):
        print("Error: client_secrets.json not found!")
        return

    credentials = None
    if os.path.exists('token.json'):
        credentials = Credentials.from_authorized_user_file('token.json', YOUTUBE_SCOPES)
        
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Refreshing existing token...")
            credentials.refresh(Request())
        else:
            print("Please check your browser to authorize this app!")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", YOUTUBE_SCOPES)
            credentials = flow.run_local_server(port=0)
            
        with open('token.json', 'w') as token:
            token.write(credentials.to_json())
            print("Successfully authenticated and saved token.json!")
    else:
        print("Already authenticated! token.json is valid.")

if __name__ == "__main__":
    auth_youtube()
