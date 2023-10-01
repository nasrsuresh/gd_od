from flask import Flask, request, redirect, session, url_for
import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from googleapiclient.http import MediaIoBaseDownload
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from requests_oauthlib import OAuth2Session

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a real secret in production
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

REDIRECT_URI = 'https://noneed.live/callback/google'
OAUTH2_CLIENT_SECRETS = 'client_secret_293814398347-e9p535ohckoja5ijpeka5ce2j6vkk5jc.apps.googleusercontent.com.json'

@app.route('/')
def home():
    return '''<a href="/auth">Start Google Drive to OneDrive Transfer</a>'''

@app.route('/auth')
def google_auth():
    flow = Flow.from_client_secrets_file(
        OAUTH2_CLIENT_SECRETS,
        scopes=['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file'],
        redirect_uri=REDIRECT_URI)

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true')

    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback/google')
def google_callback():
    state = session['state']

    flow = Flow.from_client_secrets_file(
        OAUTH2_CLIENT_SECRETS,
        scopes=[
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid',
            'https://www.googleapis.com/auth/drive.file'
        ],
        state=state,
        redirect_uri=REDIRECT_URI)

    flow.fetch_token(authorization_response=request.url)
    session['credentials'] = flow.credentials.to_dict()
    return redirect(url_for('start_transfer'))

@app.route('/start_transfer')
def start_transfer():
    creds = Credentials(**session['credentials'])
    downloaded_files = google_drive_fetch(creds)

    for file_path in downloaded_files:
        upload_to_onedrive(file_path, file_path)
    return "Transfer completed."

@app.route('/callback/microsoft')
def microsoft_callback():
    # Microsoft OAuth2 callback handling
    pass

def google_drive_fetch(credentials):
    service = build('drive', 'v3', credentials=credentials)
    results = service.files().list(pageSize=5, fields="nextPageToken, files(id, name, mimeType)").execute()
    items = results.get('files', [])
    downloaded_files = []

    if items:
        for item in items:
            file_id = item['id']
            file_name = item['name']
            file_mime = item.get('mimeType', '')

            if file_mime == "application/vnd.google-apps.document":
                request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                file_name += ".docx"
            elif file_mime == "application/vnd.google-apps.spreadsheet":
                request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                file_name += ".xlsx"
            elif file_mime == "application/vnd.google-apps.presentation":
                request = service.files().export_media(fileId=file_id, mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                file_name += ".pptx"
            else:
                request = service.files().get_media(fileId=file_id)

            counter = 1
            base_name = os.path.splitext(file_name)[0]
            while os.path.exists(file_name):
                file_name = f"{base_name}_{counter}" + os.path.splitext(file_name)[1]
                counter += 1

            with open(file_name, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            downloaded_files.append(file_name)
    return downloaded_files

def upload_to_onedrive(local_file_path, destination_path):
    client_id = 'YOUR_ONEDRIVE_CLIENT_ID'
    client_secret = 'YOUR_ONEDRIVE_CLIENT_SECRET'
    redirect_uri = 'https://noneed.live/callback/microsoft'
    authorization_base_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'

    onedrive = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=["Files.ReadWrite"])
    authorization_url, _ = onedrive.authorization_url(authorization_base_url)

    redirect_response = input('Enter the full redirected URL after authorizing the app: ')
    token = onedrive.fetch_token(token_url, client_secret=client_secret, authorization_response=redirect_response)

    headers = {"Authorization": "Bearer " + token['access_token']}
    with open(local_file_path, 'rb') as file:
        requests.put('https://graph.microsoft.com/v1.0/me/drive/root:/' + destination_path + ':/content', headers=headers, data=file)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
