import uuid
import json
import os
import ast

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

CURR_DIR = os.path.dirname(os.path.realpath(__file__))
KEYFILE_PATH = os.path.join(CURR_DIR, 'image-finder-demo-firebase-adminsdk-3kvua-934cc33dbb.json')
if os.path.exists(KEYFILE_PATH):
    CRED_INPUT = KEYFILE_PATH
else:
    CRED_INPUT = {
        "type": os.environ.get("FIREBASE_TYPE"),
        "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
        "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
        "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
        "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_X509_CERT_URL"),
        "universe_domain": os.environ.get("FIREBASE_UNIVERSE_DOMAIN")
    }

try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(CRED_INPUT)
    print('initing app....')
    firebase_admin.initialize_app(cred, {'storageBucket': 'image-finder-demo.appspot.com'})
    print('firebase initialized')


def read_data(db, user_id):
    query_logs_ref = db.collection('logs').document(user_id).collection('query_logs')
    docs = query_logs_ref.stream()

    doc_dicts = []
    for doc in docs:
        doc_dicts.append(doc.to_dict())
    return doc_dicts


def print_data(user_id):
    db = firestore.client()

    query_logs_ref = db.collection('logs').document(user_id).collection('query_logs')
    docs = query_logs_ref.stream()
    for doc in docs:
        print(f'{doc.id} => {doc.to_dict()}')


def get_and_printout_data(user_id):
    db = firestore.client()

    query_logs_ref = db.collection('logs').document(user_id).collection('query_logs')
    queries = query_logs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).get()
    for query in queries:
        print(query.id, query.to_dict())


def get_data(db, user_id):
    query_logs_ref = db.collection('logs').document(user_id).collection('query_logs')
    queries = query_logs_ref.order_by('time_stamp', direction=firestore.Query.DESCENDING).get()

    query_data = [q.to_dict() for q in queries]
    return query_data


def get_dict_list_from_json(json_file_path):
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"File not found: {json_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON file: {json_file_path}")
        return None


def get_existing_entry_times(db, user_id):
    query_data = get_data(db, user_id)
    existing_times = [e.get('req_time_stamp') for e in query_data]
    return existing_times


def get_number_of_queries(user_id):
    db = firestore.client()
    return len(read_data(db, user_id))


def firebase_store_query_log(user_id, logging_entry, db=None):
    if not db:
        db = firestore.client()

    req_time_stamp = logging_entry['time_stamp']
    input = logging_entry['input']
    rephrased_input = logging_entry['rephrased_input']
    output = logging_entry['output']
    raw_output = logging_entry['raw_output']

    query_id = req_time_stamp[5:10] + '-' + str(uuid.uuid4().hex)[6:]
    new_query_doc_ref = db.collection('logs').document(user_id).collection('query_logs').document(query_id)
    query_data = {
        'time_stamp' : firestore.SERVER_TIMESTAMP,  # Format as UTC ISO string
        'req_time_stamp' : req_time_stamp,
        'input': input,
        'rephrased_input' : rephrased_input,
        'output': output,
        'raw_output': raw_output
    }

    new_query_doc_ref.set(query_data)


def sync_log_file_to_db(db, log_json_file, step_through=False):
    #For syncing local JSON file of query logs to firebase db
    user_id = os.path.basename(log_json_file)[:5]

    existing_time_stamps = get_existing_entry_times(db, user_id)
    query_entries = get_dict_list_from_json(log_json_file)
    
    for query in query_entries:
        if step_through:
            _ = input('add entry')
        if 'time_stamp' in query:
            req_time_stamp = query['time_stamp']
        else:
            req_time_stamp = query['req_time_stamp']

        if req_time_stamp in existing_time_stamps:#TODO: do before traversal?
            continue

        if type(query['output']) == str:
            output = ast.literal_eval(query['output'])
        else:
            output = query['output']

        q = {
                "req_time_stamp" : req_time_stamp,
                "time_stamp" : firestore.SERVER_TIMESTAMP,
                "input" : query['input'],
                "rephrased_input" : query['rephrased_input'],
                "output" : output
            }
        query_id = uuid.uuid4().hex

        new_query_doc_ref = db.collection('logs').document(user_id).collection('query_logs').document(query_id)
        new_query_doc_ref.set(q)


if __name__ == "__main__":
    ...
