#!/usr/bin/env python

import base64
import xml.etree.ElementTree as ET
import subprocess
from PIL import Image
import configargparse
import re
import os
import tempfile

parser = configargparse.ArgParser(default_config_files=['config.ini'])
parser.add_argument('--frame', type=str, default='frame_desktop.svg', help='Path to the SVG frame file')
parser.add_argument('--screenshot', type=str, default='screenshots/desktop.png', help='Path to the screenshot image file')
args = parser.parse_args()

def replace_frame(frame_path, screenshot_path, output_path):
    # Load the SVG
    with open(frame_path, "r") as f:
        svg_data = f.read()

    # Parse the SVG XML
    ET.register_namespace('', "http://www.w3.org/2000/svg")  # handle default namespace
    ET.register_namespace('xlink', "http://www.w3.org/1999/xlink")
    tree = ET.ElementTree(ET.fromstring(svg_data))
    root = tree.getroot()


    # Load and encode the PNG as base64
    with open(screenshot_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    data_uri = f"data:image/png;base64,{encoded_image}"

    # Find and replace the <image> with id="screenshot"
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    for image in root.findall(".//svg:image", namespace):
        if image.attrib.get('{http://www.w3.org/1999/xlink}href') or image.attrib.get('id') == 'screenshot':
            if image.attrib.get('id') == 'screenshot':
                image.set('{http://www.w3.org/1999/xlink}href', data_uri)

    with tempfile.NamedTemporaryFile(delete=True, suffix=".svg") as intermediate_svg:
        tree.write(intermediate_svg.name, encoding="utf-8", xml_declaration=True)

        subprocess.run([
            "inkscape", intermediate_svg.name,
            "--export-type=png",
            "--export-filename=" + output_path,
        ])

def find_screenshots():
    screenshots = []

    for file in os.listdir("screenshots"):
        if file.endswith(".png") and "framed" not in file:
            with open(os.path.join("screenshots", file), "rb") as img_file:
                img = Image.open(img_file)
                width, height = img.size

                screenshots.append({
                    "name": file,
                    "width": width,
                    "height": height
                })
    
    return screenshots

def find_frames():
    frames = []

    script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    frames_dir = os.path.join(script_dir, "frames")

    print("Script directory:", script_dir)

    for frame_name in os.listdir(frames_dir):
        print(f"Checking frame: {frame_name}")

        if not frame_name.endswith(".svg"):
            continue

        pattern = 'frame-(.+)-(\\d+)x(\\d+)-(.+).svg'

        match = re.match(pattern, frame_name)

        if match:
            frame_width = int(match.group(2))
            frame_height = int(match.group(3))
        else:
            print(f"Skipping {frame_name}, does not match pattern {pattern}")
            continue

        frames.append({
            "path": os.path.join(frames_dir, frame_name),
            "width": frame_width,
            "height": frame_height
        })

    return frames

def match_screenshots_to_frames(screenshots, frames):
    for screenshot in screenshots:
        matched = False
        for frame in frames:
            if (screenshot['width'] == frame['width'] and
                screenshot['height'] == frame['height']):
                print(f"Matching {screenshot['name']} with {frame['path']}")
                replace_frame(frame['path'],
                              os.path.join("screenshots", screenshot['name']),
                              os.path.join("screenshots", screenshot['name'].replace('.png', '_framed.png')))
                matched = True
                break
        if not matched:
            print(f"No matching frame found for {screenshot['name']}, with size {screenshot['width']}x{screenshot['height']}")

frames = find_frames()

screenshots = find_screenshots()

for frame in frames:
    print(f"Found frame: {frame['path']} with size {frame['width']}x{frame['height']}")

match_screenshots_to_frames(screenshots, frames)

