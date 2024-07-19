import os
import time
import streamlit as st
import random
from PIL import Image

from retrieve import retrieve_and_return
from utils import get_image_count, query_for_related_descriptions

MAIN_DIR = os.path.dirname(os.path.realpath(__file__))
JSON_DESCRITPIONS_DIR = os.path.join(MAIN_DIR, 'json')
JSON_DESCR_SUFFIX = '_descriptions.json'
IMAGE_BASE_DIR = os.path.join(MAIN_DIR, 'image_base')
EMBEDDINGS_DIR = os.path.join(MAIN_DIR, 'embeddings')

DEPLOYED_PYTHON_PATH = '/home/adminuser/venv/bin/python'

FIXED_WIDTH = 300
FIXED_HEIGHT = 400


def send_request(prompt):
    print(f"SENDING REQUEST: {prompt}")
    print('-----')

    if prompt:
        st.session_state.history = []
        # Append user query to history
        #TODO: make retried function return that modified phrase, return that to be displayed
        st.session_state.history.append(('text', f"You: {prompt}"))
        
        try:
            images_dir = st.session_state.images_dir
            base_name = os.path.basename(images_dir)
            base_dir = os.path.dirname(os.path.dirname(images_dir))

            descriptions_folder_path = os.path.join(base_dir, 'json')
            json_file_path = os.path.join(descriptions_folder_path, base_name + JSON_DESCR_SUFFIX)
            if not os.path.exists(json_file_path):
                print('descriptions file not found, getting from firebase')

            start_t = time.perf_counter()
            output_image_names = retrieve_and_return(json_file_path, prompt, st.session_state.user_openai_api_key)
            end_t = time.perf_counter()

            retrieve_time = format(end_t - start_t, '.2f')

            st.session_state.history.append(('text', f"Found {len(output_image_names)} images in {retrieve_time} seconds"))
        except Exception as e:
            print('error during request')
            print(e)
            output_image_names = []
            st.session_state.history.append(('text', f"No results, try again."))
        
        st.session_state.search_result_images = []
        for img in output_image_names:
            img_path = os.path.join(images_dir, img)
            if os.path.exists(img_path):
                st.session_state.search_result_images.append(img_path)


def create_image_dir_name(api_key):
    return api_key[-5:]


def user_folder_exists_local(api_key):
    folder_name = create_image_dir_name(api_key)
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    image_base_dir = os.path.join(curr_dir, 'image_base')

    for f in os.listdir(image_base_dir):
        if f == folder_name:
            st.session_state.images_dir = os.path.join(image_base_dir, folder_name)
            return True
    return False


def resize_and_crop_image(image, fixed_width=FIXED_WIDTH, max_height=FIXED_HEIGHT):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(fixed_width * aspect_ratio)
    
    #resize the image to the fixed width while maintaining aspect ratio
    resized_image = image.resize((fixed_width, new_height))
    
    #crop the image if its height exceeds the max height
    if new_height > max_height:
        top = (new_height - max_height) // 2
        bottom = top + max_height
        resized_image = resized_image.crop((0, top, fixed_width, bottom))
    
    return resized_image


def resize_image(image, fixed_height=200):
    width, height = image.size

    aspect_ratio = width / height
    new_width = int(fixed_height * aspect_ratio)

    return image.resize((new_width, fixed_height))


def create_images_dict(images_dir):
    names_and_images = {}
    image_paths = [os.path.join(st.session_state.images_dir, img)
                       for img in os.listdir(images_dir) if img.endswith((".png", ".jpg", ".jpeg"))]

    for img_path in image_paths:
        opened_img = Image.open(img_path)
        cropped_img = resize_and_crop_image(opened_img)
        names_and_images[img_path] = cropped_img
    
    return names_and_images


def retrieval_page():
    images_dir = st.session_state.images_dir
    if len(st.session_state.name_and_image_dict) == 0:
        st.session_state.name_and_image_dict = create_images_dict(images_dir)

    images_count = get_image_count(images_dir)
    api_key = st.session_state.user_openai_api_key
    
    #side bar
    st.sidebar.title("Random image, try to search for this")
    random_img = random.choice(list(st.session_state.name_and_image_dict.values()))
    st.sidebar.image(random_img, use_column_width=True)

    st.text("Search through {} images".format(images_count))

    with st.form('prompt_submission'):
        text_input_col, submit_btn_col = st.columns([5, 1])
        with text_input_col:
            user_input = st.text_input(label="why is this required",
                                       label_visibility='collapsed',
                                       key="user_input",
                                       placeholder="What would you like to find?")

        with submit_btn_col:
            submit_button = st.form_submit_button(label='Send')
            
    if submit_button:
        st.session_state.init_display_images = False
        #sort by embeddings before sending request
        basename = os.path.basename(images_dir)
        embeddings_pickle_file = os.path.join(EMBEDDINGS_DIR, basename + '.pkl')

        images_ranked = query_for_related_descriptions(api_key, user_input, embeddings_pickle_file, images_dir, k=0)

        print('\n------------------------------NEW SEARCH------------------------------')

        if len(images_ranked[0]) > 1:
            st.session_state.images_ranked = images_ranked[0].tolist()
            st.session_state.all_images = [os.path.join(st.session_state.images_dir, img)
                                               for img in st.session_state.images_ranked]

        send_request(user_input)

    #display images before first submission
    if st.session_state.init_display_images:
        img_list = list(st.session_state.name_and_image_dict.values())
        for i in range(0, len(img_list), 4):
            col1, col2, col3, col4 = st.columns(4)

            i1 = img_list[i]

            col1.image(i1, use_column_width=True)
            
            if i + 1 < len(img_list):
                i2 = img_list[i+1]
                col2.image(i2, use_column_width=True)
            if i + 2 < len(img_list):
                i3 = img_list[i+2]
                col3.image(i3, use_column_width=True)
            if i + 3 < len(img_list):
                i4 = img_list[i+3]
                col4.image(i4, use_column_width=True)
    
    images_to_display = []
    for item_type, content in st.session_state.history:
        if item_type == 'text':
            st.text(content)
        elif item_type == 'image':
            images_to_display.append(content)

    for i in range(0, len(st.session_state.search_result_images), 2):
        col1, col2 = st.columns(2)

        res_img = st.session_state.name_and_image_dict[st.session_state.search_result_images[i]]
        col1.image(res_img, use_column_width=True, caption="top result")
        
        if i + 1 < len(st.session_state.search_result_images):
            res_img = st.session_state.name_and_image_dict[st.session_state.search_result_images[i+1]]
            col2.image(res_img, use_column_width=True, caption='top result')

    #display rest of images in ranked order
    if not st.session_state.init_display_images:
        remaining_images = [img for img in st.session_state.all_images
                                if img not in st.session_state.search_result_images]
    else:
        remaining_images = []
    
    for i in range(0, len(remaining_images), 4):
        col1, col2, col3, col4 = st.columns(4)

        i1 = st.session_state.name_and_image_dict[remaining_images[i]]

        col1.image(i1, use_column_width=True)
        
        if i + 1 < len(remaining_images):
            i2 = st.session_state.name_and_image_dict[remaining_images[i+1]]
            col2.image(i2, use_column_width=True)
        if i + 2 < len(remaining_images):
            i3 = st.session_state.name_and_image_dict[remaining_images[i+2]]
            col3.image(i3, use_column_width=True)
        if i + 3 < len(remaining_images):
            i4 = st.session_state.name_and_image_dict[remaining_images[i+3]]
            col4.image(i4, use_column_width=True)


def main():
    st.title('PhotoFind Public Demo')
    footer = """
        <style>
            .footer {
                position: fixed;
                left: 0;
                bottom: 0;
                width: 100%;
                background-color: #111;
                color: white;
                text-align: center;
            }
        </style>
        <div class="footer">
            <p>By Cade Hutcheson</p>
        </div>
    """
    st.markdown(footer, unsafe_allow_html=True)

    retrieval_page()


def make_st_vars():
    #app start point
    if 'user_openai_api_key' not in st.session_state:
        st.session_state.user_openai_api_key = os.environ["PUBLIC_DEMO_KEY"]

    if 'history' not in st.session_state:
        st.session_state.history = []

    if 'all_images' not in st.session_state:
        st.session_state.all_images = []

    if 'images_dir' not in st.session_state:
        key_dirname = create_image_dir_name(st.session_state.user_openai_api_key)
        st.session_state.images_dir = os.path.join(IMAGE_BASE_DIR, key_dirname)

    if 'images_ranked' not in st.session_state:
        st.session_state.images_ranked  = []

    if 'search_result_images' not in st.session_state:
        st.session_state.search_result_images = []
    
    if 'name_and_image_dict' not in st.session_state:
        st.session_state.name_and_image_dict = dict()

    if 'init_display_images' not in st.session_state:
        st.session_state.init_display_images = True

make_st_vars()
main()
