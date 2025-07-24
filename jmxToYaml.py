from flask import Flask, request, jsonify
import os
import tempfile
import xml.etree.ElementTree as ET
import yaml

app = Flask(__name__)

def extract_headers(sampler_elem):
    headers = {}
    parent_hash_tree = sampler_elem.getparent() if hasattr(sampler_elem, "getparent") else sampler_elem.find("..")

    if parent_hash_tree is not None:
        siblings = list(parent_hash_tree)
        sampler_index = siblings.index(sampler_elem)

        if sampler_index + 1 < len(siblings):
            next_elem = siblings[sampler_index + 1]
            if next_elem.tag == "hashTree":
                header_manager = next_elem.find(".//HeaderManager")
                if header_manager is not None:
                    collection = header_manager.find("collectionProp[@name='HeaderManager.headers']")
                    if collection is not None:
                        for header_elem in collection.findall("elementProp"):
                            name_elem = header_elem.find("stringProp[@name='Header.name']")
                            value_elem = header_elem.find("stringProp[@name='Header.value']")
                            if name_elem is not None and value_elem is not None:
                                headers[name_elem.text] = value_elem.text
    return headers

@app.route('/convert', methods=['POST'])
def convert_jmx_to_yaml():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if not file.filename.endswith('.jmx'):
        return jsonify({'error': 'Only .jmx files are allowed'}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jmx") as tmp:
        file_path = tmp.name
        file.save(file_path)

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Register namespaces to avoid ns issues
        ET.register_namespace('', "http://jmeter.apache.org/")

        result = {'api_tests': []}

        for sampler in root.iter('HTTPSamplerProxy'):
            sampler_name = sampler.attrib.get('testname', 'unknown_api')

            method = sampler.findtext(".//stringProp[@name='HTTPSampler.method']", default='GET')
            domain = sampler.findtext(".//stringProp[@name='HTTPSampler.domain']", default='')
            path = sampler.findtext(".//stringProp[@name='HTTPSampler.path']", default='')
            protocol = sampler.findtext(".//stringProp[@name='HTTPSampler.protocol']", default='http')

            # Construct full URL
            url = f"{protocol}://{domain}/{path}".replace('//', '/').replace(':/', '://')

            # Get payload (argument.value)
            payload = ''
            for arg_val in sampler.findall(".//elementProp[@name='argument']/stringProp[@name='Argument.value']"):
                if arg_val.text:
                    payload += arg_val.text.strip()

            headers = extract_headers(sampler)

            result['api_tests'].append({
                'api_name': sampler_name,
                'headers': headers,
                'method': method,
                'payload': payload,
                'status_code': 200,
                'url': url,
                'repeat': 1
            })

        yaml_output = yaml.dump(result, sort_keys=False)
        return yaml_output, 200, {'Content-Type': 'text/yaml'}

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.remove(file_path)

if __name__ == '__main__':
    app.run(debug=True)
