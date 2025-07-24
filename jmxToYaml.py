from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
import yaml
import os
import tempfile

app = Flask(__name__)

def parse_jmx(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    namespace = ''  # No namespace used

    api_tests = []

    for sampler in root.iter('HTTPSamplerProxy'):
        api_name = sampler.attrib.get('testname', 'UnknownAPI')
        method = sampler.findtext(".//stringProp[@name='HTTPSampler.method']", default='GET')
        domain = sampler.findtext(".//stringProp[@name='HTTPSampler.domain']", default='')
        path = sampler.findtext(".//stringProp[@name='HTTPSampler.path']", default='')
        url = f"https://{domain}{path}" if domain else path
        payload = sampler.findtext(".//stringProp[@name='Argument.value']", default='{}').replace('&quot;', '"').strip()

        # Headers
        headers = {}
        header_manager = sampler.find("./hashTree/HeaderManager/collectionProp")
        if header_manager is not None:
            for element in header_manager.findall("elementProp"):
                name = element.findtext("stringProp[@name='Header.name']")
                value = element.findtext("stringProp[@name='Header.value']")
                if name and value:
                    headers[name] = value

        # Repeat
        repeat = 1
        parent = sampler.getparent() if hasattr(sampler, "getparent") else None
        loop_controller = sampler.find(".//intProp[@name='LoopController.loops']")
        if loop_controller is not None:
            try:
                repeat = int(loop_controller.text)
            except:
                pass

        api_tests.append({
            'api_name': api_name,
            'headers': headers,
            'method': method,
            'payload': payload,
            'status_code': 200,
            'url': url,
            'repeat': repeat
        })

    return {'api_tests': api_tests}

@app.route('/convert', methods=['POST'])
def convert_jmx():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename.endswith('.jmx'):
        return jsonify({'error': 'Only .jmx files are allowed'}), 400

    file_path = tempfile.maketemp(suffix='.jmx')
    file.save(file_path)

    try:
        data = parse_jmx(file_path)
        yaml_output = yaml.dump(data, sort_keys=False)
        return yaml_output, 200, {'Content-Type': 'text/yaml'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        os.remove(file_path)

if __name__ == '__main__':
    app.run(debug=True)