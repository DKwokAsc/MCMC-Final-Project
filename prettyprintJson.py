import json

# Load the JSON data from a file
with open('wi_2024_gen_prec_graph.json', 'r') as f:
    data = json.load(f)

with open('pretty_print.json', 'w') as f:
    json.dump(data, f, indent=4)