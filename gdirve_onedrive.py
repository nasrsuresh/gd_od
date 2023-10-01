from flask import Flask, request, redirect, session, url_for
import os
import os.path
import pickle
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from requests_oauthlib import OAuth2Session
from googleapiclient.http import MediaIoBaseDownload
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a real secret in production

REDIRECT_URI ='https://noneed.live/callback/google'
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
    print(request.scheme)
    state = session['state']
    
    flow = Flow.from_client_secrets_file(
        OAUTH2_CLIENT_SECRETS,
        scopes=['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file'],
        state=state,
        redirect_uri=REDIRECT_URI)
    
    flow.fetch_token(authorization_response=request.url)
    
    session['credentials'] = flow.credentials.to_dict()
    
    return redirect(url_for('start_transfer'))

@app.route('/start_transfer')
def start_transfer():
    if 'credentials' not in session:
        return redirect(url_for('google_auth'))
    creds = Credentials(**session['credentials'])
    downloaded_files = google_drive_fetch(creds)
    
    if downloaded_files:
        for file_path in downloaded_files:
            upload_to_onedrive(file_path, file_path)
        return "Transfer completed."
    else:
        return "No files fetched from Google Drive."


# Similarly, for OneDrive's OAuth2
@app.route('/callback/microsoft')
def microsoft_callback():
    # Handle the callback from Microsoft here
    pass
# Google Drive Authentication & File Fetch
def google_drive_auth():
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']
    creds = None

    # Forcefully delete the token.pickle file for re-authentication
    if os.path.exists('token.pickle'):
        os.remove('token.pickle')
    
    flow = InstalledAppFlow.from_client_secrets_file('client_secret_293814398347-e9p535ohckoja5ijpeka5ce2j6vkk5jc.apps.googleusercontent.com.json', SCOPES)
    creds = flow.run_local_server(port=50906)
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(pageSize=5, fields="nextPageToken, files(id, name, mimeType)").execute()
    items = results.get('files', [])

    downloaded_files = []

    if items:
        for item in items:
            print(item)
            
            file_id = item['id']
            file_name = item['name']
            file_mime = item.get('mimeType', '')

            # If there's no MIME type, attempt to infer it from the name
            if not file_mime:
                if file_name.endswith('.gsheet'):
                    file_mime = "application/vnd.google-apps.spreadsheet"
                else:
                    print(f"ERROR: No MIME type found for the file {file_name} and couldn't infer from name.")
                    continue
            
            # Check file type
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

            # Avoid overwriting by checking if a file with the same name exists and renaming it
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
                    if not done:
                        print(fh.tell())  # Number of bytes downloaded so far

            downloaded_files.append(file_name)

    return downloaded_files

# OneDrive Authentication & File Upload
def upload_to_onedrive(local_file_path, destination_path):
    client_id = '7347f1a0-d50f-4020-83b7-d360b49daaf9'
    client_secret = 'jAr8Q~Lr2mj1ftvDbZ6iL3nqZI.idM7xfBLN-a_f'
    redirect_uri = 'http://localhost:8080/'
    authorization_base_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    token_url = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'

    onedrive = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=["Files.ReadWrite"])
    authorization_url, _ = onedrive.authorization_url(authorization_base_url)
    print('Please go to the following URL and authorize the app:', authorization_url)

    # Capture the redirect URL directly from the user input
    redirect_response = input('Enter the full redirected URL after authorizing the app: ')
    
    token = onedrive.fetch_token(token_url, client_secret=client_secret, authorization_response=redirect_response)

    headers = {"Authorization": "Bearer " + token['access_token']}
    with open(local_file_path, 'rb') as file:
        requests.put('https://graph.microsoft.com/v1.0/me/drive/root:/' + destination_path + ':/content', headers=headers, data=file)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)



