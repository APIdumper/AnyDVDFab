import re
import secrets
from random import SystemRandom

import requests

from flask import Flask, request, Response
from requests_toolbelt import MultipartEncoder

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SECRET_KEY=secrets.token_hex(16),
    ALLOWED_HOSTS=['127.0.0.1', 'localhost']
)


def parse_boundary(data: str) -> dict:
    """
    Parse the multipart form data to extract fields.

    Parameters:
    - data (str): The raw multipart form data as a string.

    Returns:
    - dict: A dictionary with form field names as keys and field values as values.
    """
    fields = {}
    # Split parts using the boundary (separator) and process each part
    items = data.split('-' * 26)[1:]
    for item in items:
        lines = item.splitlines()
        if len(lines) < 3:
            continue
        # Extract the field name from the Content-Disposition header
        key = re.match(r'^Content-Disposition:\s*form-data;\s*name="([^"]+)"\s*$', lines[1]).group(1)
        # Join the remaining lines as the field value
        fields[key] = '\n'.join(lines[3:])
    return fields


def patch_boundary(data: dict) -> dict:
    """
    Modify specific fields in the data dictionary based on predefined rules.

    Parameters:
    - data (dict): A dictionary containing form field names and values.

    Returns:
    - dict: The modified dictionary with updated field values.
    """
    # Generate a new machine ID
    machine_id = [''.join(SystemRandom().choice('abcdef0123456789') for _ in range(2)) for _ in range(12)]
    machine_id = ':'.join(['-'.join(machine_id[:6]), '-'.join(machine_id[6:])])

    # Update fields based on rules
    for key, value in data.items():
        if key in ('TK', 'PW', 'D', 'F') and re.match(r'[0-9a-f]{32}', value):
            data[key] = value  # ''  # Replace token
        if re.match(r'^([0-9a-f]{2}-){5}[0-9a-f]{2}:([0-9a-f]{2}-){5}[0-9a-f]{2}', value):
            data[key] = machine_id  # Replace MAC
        elif re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value):
            fake_email_user = ''.join(SystemRandom().choice('abcdefghijklmnopqrstuvwxyz.-0123456789') for _ in range(SystemRandom().randint(8, 16)))
            fake_email_provider = SystemRandom().choice(["@gmail.com", "@hotmail.com", "@yahoo.com"])
            data[key] = fake_email_user + fake_email_provider  # Replace email
        elif re.match(r'^365$', value):
            data[key] = 'trial'  # Replace subscription

    return data


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['POST'])
def catch_all(path: str) -> Response:
    """
    Handle all POST requests, modify the data, and forward it to the same URL over HTTPS.

    Parameters:
    - path (str): The path part of the URL (used for routing).

    Returns:
    - Response: A Flask Response object with the status and content of the forwarded request.
    """
    # Get the raw request data
    body = request.get_data().decode('utf-8')

    # Parse the multipart form data and modify it
    boundary = parse_boundary(body)
    patched = patch_boundary(boundary)

    # Create a MultipartEncoder with the modified data
    mp_encoder = MultipartEncoder(patched)

    # Prepare headers for the forwarded request
    headers = dict(request.headers)
    del headers['Connection']
    del headers['Content-Length']
    headers['Content-Type'] = mp_encoder.content_type

    # Forward the request to the same URL over HTTPS
    r = requests.request(
        method=request.method,
        url=request.url.replace('http://', 'https://'),
        params=request.args.to_dict(),
        data=mp_encoder,
        headers=headers,
        cookies=request.cookies
    )

    # Return the response from the forwarded request
    return Response(status=r.status_code, response=r.content)


# Run the Flask app
app.add_url_rule('/', 'catch_all', catch_all, defaults={'path': ''})
app.add_url_rule('/<path:path>', 'catch_all', catch_all, defaults={'path': ''})
app.run(host='127.0.0.1', port=5000)
