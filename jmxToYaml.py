from flask import Flask, request, jsonify
import xml.etree.ElementTree as ET
import yaml

app = Flask(__name__)

@app.route('/parse-jmx', methods=['POST'])
def parse_jmx():
    file = request.files.get('jmx_file')
    if not file or not file.filename.endswith('.jmx'):
        return jsonify({"error": "Please upload a valid .jmx file"}), 400

    try:
        tree = ET.parse(file)
        root = tree.getroot()

        api_tests = []

        thread_groups = list(root.iter("ThreadGroup"))
        all_elements = list(root)

        for i, tg in enumerate(thread_groups):
            tg_index = all_elements.index(tg)
            if tg_index + 1 >= len(all_elements):
                continue

            tg_hash_tree = all_elements[tg_index + 1]

            for j, child in enumerate(tg_hash_tree):
                if child.tag == "TransactionController":
                    tx_hash_tree = tg_hash_tree[j + 1] if j + 1 < len(tg_hash_tree) else None
                    if tx_hash_tree is not None:
                        tx_samplers = list(tx_hash_tree)
                        k = 0
                        while k < len(tx_samplers):
                            sampler = tx_samplers[k]
                            if sampler.tag == "HTTPSamplerProxy":
                                api_name = sampler.attrib.get("testname", "UnnamedAPI")
                                method = get_text(sampler, 'HTTPSampler.method')
                                domain = get_text(sampler, 'HTTPSampler.domain')
                                protocol = get_text(sampler, 'HTTPSampler.protocol')
                                path = get_text(sampler, 'HTTPSampler.path')
                                url = f"{protocol}://{domain}/{path}".replace('//', '/').replace(':/', '://')

                                # Get payload
                                payload = ""
                                for arg in sampler.findall(".//elementProp"):
                                    for string_prop in arg.findall("stringProp"):
                                        if string_prop.attrib.get("name") == "Argument.value":
                                            payload = string_prop.text or ""

                                # Get headers from sampler's next hashTree
                                headers = {}
                                if k + 1 < len(tx_samplers):
                                    sampler_hash = tx_samplers[k + 1]
                                    header_manager = sampler_hash.find(".//HeaderManager")
                                    if header_manager is not None:
                                        for header in header_manager.findall(".//elementProp"):
                                            name = header.findtext("stringProp[@name='Header.name']")
                                            value = header.findtext("stringProp[@name='Header.value']")
                                            if name and value:
                                                headers[name] = value

                                # Append to list
                                api_tests.append({
                                    "api_name": api_name,
                                    "headers": headers,
                                    "method": method,
                                    "payload": payload,
                                    "status_code": 200,
                                    "url": url,
                                    "repeat": 1
                                })

                                k += 2  # Skip hashTree
                            else:
                                k += 1

        full_output = {"api_tests": api_tests}
        yaml_output = yaml.dump(full_output, sort_keys=False)

        return jsonify({
            "json_data": full_output,
            "yaml_data": yaml_output
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_text(parent, prop_name):
    elem = parent.find(f".//stringProp[@name='{prop_name}']")
    return (elem.text or '').strip() if elem is not None else ''


if __name__ == '__main__':
    app.run(debug=True)
