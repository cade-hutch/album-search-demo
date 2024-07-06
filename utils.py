import os
import json
import pickle
import faiss
from datetime import datetime
import numpy as np

from langchain_community.embeddings import OpenAIEmbeddings

MAIN_DIR = os.path.dirname(os.path.realpath(__file__))
EMBEDDINGS_DIR = os.path.join(MAIN_DIR, 'embeddings')


def get_image_count(images_dir):
    #jpg/pngs only
    images_count = 0
    for file in os.listdir(images_dir):
        if file.endswith('.png') or file.endswith('.jpg') or file.endswith('.jpeg'):
            images_count += 1
    return images_count


def validate_openai_api_key(api_key):
    ...

def get_descr_filepath(images_dir):
    basename = os.path.basename(images_dir)
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    descr_filepath = os.path.join(curr_dir, 'json', basename + '_descriptions.json')
    return descr_filepath


def retrieve_contents_from_json(json_file_path):
    #return list of dicts(keys = filename, value = descr)
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


#logging utils
def create_logging_entry(input, rephrased_input, output, raw_output):
    current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {'time_stamp' : current_date_time, 'input' : input, 'rephrased_input' : rephrased_input, 'output' : output, 'raw_output' : raw_output}


def store_logging_entry(logging_file, entry):
    #save a new single entry to a json logging file
    if not os.path.exists(os.path.dirname(logging_file)):
        os.mkdir(os.path.dirname(logging_file))

    try:
        with open(logging_file, 'r') as file:
            if os.path.getsize(logging_file) != 0:
              existing_data = json.load(file)
            else:
                existing_data = []
    except FileNotFoundError:
        existing_data = []
        print('logging store: error getting existing')

    existing_data.append(entry)

    #write the combined data back to the file
    with open(logging_file, 'w') as file:
        json.dump(existing_data, file, indent=2)



def add_new_descr_to_embedding_pickle(embeddings_obj, pickle_file, descriptions, create_new=False):
    #one or multiple descr
    #NOTE: np array additions must have same amount of columns(1536)
    if not create_new:
        with open(pickle_file, 'rb') as file:
            existing_embeddings = pickle.load(file)
    else:
        existing_embeddings = []

    if type(descriptions) == str:
        descriptions = [descriptions]

    new_rows = []
    for descr in descriptions:
        new_row = create_single_embedding(embeddings_obj, descr)
        new_rows.append(new_row)

    new_rows = np.array(new_rows).astype('float32')

    if create_new:
        new_embeddings = new_rows
    else:
        new_embeddings = np.vstack((existing_embeddings, new_rows))

    with open(pickle_file, 'wb') as file:
        pickle.dump(new_embeddings, file)


def create_single_embedding(embeddings_obj, description):
    return embeddings_obj.embed_query(description)


def query_for_related_descriptions(api_key, query, embeddings_pickle_file, images_dir, k=10):
    json_descr_filepath = get_descr_filepath(images_dir)
    json_dict = retrieve_contents_from_json(json_descr_filepath)
    
    file_names = list(json_dict.keys())
    descriptions = list(json_dict.values())

    embeddings_obj = OpenAIEmbeddings(api_key=api_key)

    if not os.path.exists(embeddings_pickle_file):
        add_new_descr_to_embedding_pickle(embeddings_obj, embeddings_pickle_file, descriptions, create_new=True)

    if k == 0:
        k = len(file_names)

    embeddings_list = get_embeddings_from_pickle_file(embeddings_pickle_file)
    index = faiss.IndexFlatL2(1536)
    index.add(embeddings_list)

    query_embedding = embeddings_obj.embed_query(query)
    query_embedding = np.array([query_embedding]).astype('float32')

    distances, indices = index.search(query_embedding, k)

    images_ranked = np.array(file_names)[indices]
    return images_ranked


def query_and_filter(api_key, embeddings_pickle_file, descriptions_dict, query, filter):
    file_names = list(descriptions_dict.keys())
    descriptions = list(descriptions_dict.values())

    embeddings_obj = OpenAIEmbeddings(api_key=api_key)

    k = int(len(descriptions) * filter)
    embeddings_list = get_embeddings_from_pickle_file(embeddings_pickle_file)
    index = faiss.IndexFlatL2(1536)
    index.add(embeddings_list)

    query_embedding = embeddings_obj.embed_query(query)
    query_embedding = np.array([query_embedding]).astype('float32')

    distances, indices = index.search(query_embedding, k)

    images_ranked = np.array(file_names)[indices]
    search_ouput = np.array(descriptions)[indices]

    return images_ranked



def rank_and_filter_descriptions(api_key, descriptions_dict, prompt, filter=1.0):
    """
    helper function for retrieve_and_return. get descriptions dictionary from descriptions json file.
    """
    if filter > 1.0 or filter <= 0.0:
        filter = 1

    pickle_file = os.path.join(EMBEDDINGS_DIR, api_key[-5:] + ".pkl")
    if not os.path.exists(pickle_file):
        assert False, "rank_and_filter_descriptions: no pickle file "
    
    #embeddings search -> return top percentage of ranked descriptions based on filter value
    filtered_images = query_and_filter(api_key, pickle_file, descriptions_dict, prompt, filter)[0]
    filtered_descr_dict = dict()
    for img in list(filtered_images):
        filtered_descr_dict[img] = descriptions_dict[img]

    return filtered_descr_dict


def get_embeddings_from_pickle_file(pickle_file):
    with open(pickle_file, 'rb') as file:
        embeddings_list = pickle.load(file)
    return embeddings_list

