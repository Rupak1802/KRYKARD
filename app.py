import streamlit as st
import os
from dotenv import load_dotenv
from hd_image_generator import generate_hd_image
from PIL import Image, ImageEnhance, ImageFilter
import io
import requests
import base64
import time
import pandas as pd

load_dotenv()
API_KEY = os.getenv("BRIA_API_KEY")

st.set_page_config(page_title="KRYKARD Image Generator", page_icon="images/favicon(1).png")

def set_background(image_file):
    with open(image_file, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{encoded_string}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def save_feedback(prompt: str, image_url: str, feedback: str):
    feedback_file = "feedback.csv"
    new_row = {
        "prompt": prompt,
        "image_url": image_url,
        "feedback": feedback
    }
    if os.path.exists(feedback_file):
        df = pd.read_csv(feedback_file)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
    df.to_csv(feedback_file, index=False)

set_background("images/background.png")

col1, col2 = st.columns([100, 182])
with col1:
    st.image("images/favicon(1).png", width=250)
with col2:
    st.markdown("<h1 style='margin-top: 10px;'>KRYKARD Image Generator</h1>", unsafe_allow_html=True)

if "last_image_bytes" not in st.session_state:
    st.session_state.last_image_bytes = None
if "edited_image_bytes" not in st.session_state:
    st.session_state.edited_image_bytes = None
if "urls" not in st.session_state:
    st.session_state.urls = []

prompt = st.text_area("Enter your image prompt:", height=200)

col1, col2, col3 = st.columns(3)
with col1:
    num_images = st.slider("Number of images", 1, 4, 1)
with col2:
    aspect_ratio = st.selectbox("Aspect Ratio", ["1:1", "16:9", "9:16", "4:3", "3:4"])
with col3:
    enhance_quality = st.checkbox("Enhance Image", True)

style = st.selectbox("Image Style", ["Realistic", "Artistic", "Cartoon", "Sketch", "Oil Painting", "Watercolor"])
if style != "Realistic":
    prompt = f"{prompt}, in {style.lower()} style"

if st.button("Generate Image"):
    if not API_KEY:
        st.error("BRIA_API_KEY is missing in your .env file.")
    elif not prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Generating image..."):
            try:
                max_retries = 3
                result = None
                for attempt in range(max_retries):
                    try:
                        result = generate_hd_image(
                            prompt=prompt,
                            api_key=API_KEY,
                            num_results=num_images,
                            aspect_ratio=aspect_ratio,
                            enhance_image=enhance_quality,
                            medium="art" if style != "Realistic" else "photography",
                            sync=True
                        )
                        break
                    except Exception as e:
                        if "504" in str(e) and attempt < max_retries - 1:
                            st.warning(f"Server timeout (504). Retrying... ({attempt + 1}/{max_retries})")
                            time.sleep(2)
                        else:
                            st.error(f"Generation Error: {e}")
                            break

                urls = []
                if result:
                    if "result_urls" in result:
                        urls = result["result_urls"]
                    elif "result_url" in result:
                        urls = [result["result_url"]]
                    elif "result" in result and isinstance(result["result"], list):
                        for item in result["result"]:
                            if isinstance(item, dict) and "urls" in item:
                                urls.extend(item["urls"])

                if urls:
                    st.session_state.urls = urls
                    st.session_state.last_image_bytes = requests.get(urls[0]).content
                else:
                    st.error("No images returned.")

            except Exception as e:
                st.error(f"Generation Error: {e}")

if st.session_state.urls:
    for i, img_url in enumerate(st.session_state.urls):
        img_data = requests.get(img_url).content
        st.image(img_data, caption=f"Generated Image {i + 1}", use_column_width=True)
        st.download_button(
            label=f"Download Image {i + 1}",
            data=img_data,
            file_name=f"image_{i + 1}.png",
            mime="image/png"
        )
        feedback_col1, feedback_col2 = st.columns(2)
        with feedback_col1:
            if st.button(f"Like Image {i + 1}", key=f"like_{i}"):
                save_feedback(prompt, img_url, "like")
                st.success("Thanks for your feedback!")
        with feedback_col2:
            if st.button(f"Dislike Image {i + 1}", key=f"dislike_{i}"):
                save_feedback(prompt, img_url, "dislike")
                st.success("Thanks for your feedback!")

if st.session_state.last_image_bytes:
    st.markdown("---")
    st.subheader("Edit Image")

    edit_option = st.selectbox("Choose an edit", [
        "No Edit",
        "Grayscale",
        "Sepia",
        "High Contrast",
        "Blur"
    ])

    if st.button("Apply Edit"):
        try:
            image = Image.open(io.BytesIO(st.session_state.last_image_bytes))
            if edit_option == "Grayscale":
                image = image.convert("L")
            elif edit_option == "Sepia":
                sepia = image.convert("RGB")
                width, height = sepia.size
                pixels = sepia.load()
                for py in range(height):
                    for px in range(width):
                        r, g, b = sepia.getpixel((px, py))
                        tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                        tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                        tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                        pixels[px, py] = (min(tr, 255), min(tg, 255), min(tb, 255))
                image = sepia
            elif edit_option == "High Contrast":
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(2.0)
            elif edit_option == "Blur":
                image = image.filter(ImageFilter.BLUR)

            output = io.BytesIO()
            image.save(output, format="PNG")
            st.session_state.edited_image_bytes = output.getvalue()

            st.image(st.session_state.edited_image_bytes, caption="Edited Image", use_column_width=True)
            st.download_button(
                label="Download Edited Image",
                data=st.session_state.edited_image_bytes,
                file_name="edited_image.png",
                mime="image/png"
            )

        except Exception as e:
            st.error(f"Edit failed: {e}")
