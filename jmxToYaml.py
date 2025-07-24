from flask import Flask, request, jsonify
import tempfile
import xml.etree.ElementTree as ET
import yaml
import os

app = Flask(__name__)

# Utility: Extract headers from sibling hashTree of HTTPSamplerProxy
def extract_headers(sampler_elem, parent_hash_tree):
    headers = {}
    if parent_hash_tree is not None:
        siblings = list(parent_hash_tree)
        sampler_index = siblings.index(sampler_elem)

        # Look for next sibling hashTree
        if sampler_index + 1 < len(siblings):
            sampler_hash_tree = siblings[sampler_index + 1]
            header_manager = sampler_hash_tree.find(".//HeaderManager")
            if header_manager is not None:
                collection = header_manager.find("collectionProp[@name='HeaderManager.headers']")
                if collection is not None:
                    for header_elem in collection.findall("elementProp"):
                        name_elem = header_elem.find("stringProp[@name='Header.name']")
                        value_elem = header_elem.find("stringProp[@name='Header.value']")
                        if name_elem is not None and value_elem is not None:
                            headers[name_elem.text] = value_elem.text
    return headers

# Utility: Extract payload from sampler itself
def extract_payload(sampler):
    payload = ""
    arguments = sampler.find(".//elementProp[@name='HTTPsampler.Arguments']")
    if arguments is not None:
        for arg_val in arguments.findall(".//stringProp[@name='Argument.value']"):
            if arg_val.text:
                payload += arg_val.text.strip()
    return payload

@app.route('/parse-jmx', methods=['POST'])
def parse_jmx():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    # Save the uploaded file to a temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jmx') as temp_file:
        file.save(temp_file.name)
        temp_path = temp_file.name

    try:
        tree = ET.parse(temp_path)
        root = tree.getroot()

        test_plan = []

        for parent in root.iter():
            for sampler in parent.findall("HTTPSamplerProxy"):
                method = sampler.findtext("stringProp[@name='HTTPSampler.method']")
                url = sampler.findtext("stringProp[@name='HTTPSampler.path']")
                payload = extract_payload(sampler)
                headers = extract_headers(sampler, parent)

                transaction = {
                    "request": {
                        "method": method,
                        "url": url,
                        "headers": headers or {},
                        "body": payload or ""
                    }
                }

                test_plan.append(transaction)

        os.remove(temp_path)

        # Return YAML response
        yaml_output = yaml.dump(test_plan, sort_keys=False)
        return app.response_class(yaml_output, content_type='text/yaml')

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    app.run(debug=True)
